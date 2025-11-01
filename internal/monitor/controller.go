package monitor

import (
	"bytes"
	"encoding/json"
	"fmt" // <-- ADDED for pod key
	"io"
	"log"
	"net/http"
	"sync" // <-- ADDED for mutex
	"time"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/client-go/informers"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/tools/cache"
)

// alertWaitPeriod is the duration to wait before re-alerting for the same pod
const alertWaitPeriod = 2 * time.Hour

// Controller holds the clientset and the informer
type Controller struct {
	Clientset kubernetes.Interface
	Informer  cache.SharedIndexInformer

	// --- NEW: Cache for rate limiting ---
	alertCache map[string]time.Time
	cacheMutex sync.RWMutex
}

// NewController creates a new controller
func NewController(clientset *kubernetes.Clientset) *Controller {

	// --- THIS IS THE FIXED LINE ---
	factory := informers.NewSharedInformerFactory(clientset, 10*time.Minute)
	podInformer := factory.Core().V1().Pods().Informer()

	c := &Controller{
		Clientset: clientset,
		Informer:  podInformer,

		// --- NEW: Initialize the cache and mutex ---
		alertCache: make(map[string]time.Time),
		cacheMutex: sync.RWMutex{},
	}

	podInformer.AddEventHandler(cache.ResourceEventHandlerFuncs{
		AddFunc:    c.onAdd,
		UpdateFunc: c.onUpdate,
	})

	return c
}

// Run starts the controller's informer
func (c *Controller) Run(stopCh <-chan struct{}) {
	// ... (this function is unchanged)
	log.Println("Starting monitor controller...")
	go c.Informer.Run(stopCh)

	if !cache.WaitForCacheSync(stopCh, c.Informer.HasSynced) {
		log.Fatalf("failed to sync cache")
		return
	}
	log.Println("Controller cache synced")

	<-stopCh
	log.Println("Stopping monitor controller...")
}

// onAdd is called when a pod is added
func (c *Controller) onAdd(obj interface{}) {
	pod := obj.(*corev1.Pod)
	if isBad, reason := checkPodBadState(pod); isBad {
		log.Printf("TRIGGER_CHECK: New pod %s/%s is in bad state: %s", pod.Namespace, pod.Name, reason)
		c.checkAndTrigger(pod, reason)
	}
}

// onUpdate is called when a pod is modified
func (c *Controller) onUpdate(oldObj, newObj interface{}) {
	oldPod := oldObj.(*corev1.Pod)
	newPod := newObj.(*corev1.Pod)

	wasBad, _ := checkPodBadState(oldPod)
	isBad, reason := checkPodBadState(newPod)

	if !wasBad && isBad {
		log.Printf("TRIGGER_CHECK: Pod %s/%s has entered bad state: %s", newPod.Namespace, newPod.Name, reason)
		c.checkAndTrigger(newPod, reason)
	}
}

// --- NEW FUNCTION: checkAndTrigger ---
func (c *Controller) checkAndTrigger(pod *corev1.Pod, reason string) {
	podKey := fmt.Sprintf("%s/%s", pod.Namespace, pod.Name)

	c.cacheMutex.RLock()
	lastAlertTime, exists := c.alertCache[podKey]
	c.cacheMutex.RUnlock()

	if exists && time.Since(lastAlertTime) < alertWaitPeriod {
		log.Printf(
			"SUPPRESSED ALERT for %s. Last alert was at %v (within %v).",
			podKey,
			lastAlertTime,
			alertWaitPeriod,
		)
		return
	}

	c.cacheMutex.Lock()
	c.alertCache[podKey] = time.Now()
	c.cacheMutex.Unlock()

	c.triggerAnalysis(pod, reason)
}

// checkPodBadState checks for various failure conditions
func checkPodBadState(pod *corev1.Pod) (bool, string) {
	if pod.Status.Phase == corev1.PodFailed {
		return true, "PodFailed"
	}

	for _, containerStatus := range pod.Status.ContainerStatuses {
		if containerStatus.State.Waiting != nil {
			reason := containerStatus.State.Waiting.Reason
			if reason == "CrashLoopBackOff" || reason == "ImagePullBackOff" || reason == "ErrImagePull" {
				return true, reason
			}
		}
		if containerStatus.State.Terminated != nil {
			if containerStatus.State.Terminated.Reason == "Error" {
				return true, "Terminated(Error)"
			}
		}
	}
	return false, ""
}

// triggerAnalysis calls our Python AI agent service
func (c *Controller) triggerAnalysis(pod *corev1.Pod, reason string) {
	agentURL := "http://localhost:8000/summarize-pod"

	log.Printf("Triggering analysis for pod: %s/%s (Reason: %s)", pod.Namespace, pod.Name, reason)

	payload := map[string]string{
		"namespace": pod.Namespace,
		"pod_name":  pod.Name,
		"reason":    reason,
	}
	jsonPayload, err := json.Marshal(payload)
	if err != nil {
		log.Printf("ERROR: Failed to marshal JSON for pod %s: %v", pod.Name, err)
		return
	}

	req, err := http.NewRequest("POST", agentURL, bytes.NewBuffer(jsonPayload))
	if err != nil {
		log.Printf("ERROR: Failed to create request for pod %s: %v", pod.Name, err)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("ERROR: Failed to send request to agent for pod %s: %v", pod.Name, err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Printf("ERROR: Agent service returned non-200 status: %s", resp.Status)
		body, _ := io.ReadAll(resp.Body)
		log.Printf("Agent error response: %s", string(body))
		return
	}

	log.Printf("Successfully triggered analysis for %s/%s. Agent responded: %s", pod.Namespace, pod.Name, resp.Status)
}
