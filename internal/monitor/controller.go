package monitor

import (
	"bytes"
	"encoding/json"
	"io"

	//"fmt" // Import fmt for Sprintf
	"log"
	"net/http"
	"time"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/client-go/informers"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/tools/cache"
)

// Controller holds the clientset and the informer
type Controller struct {
	Clientset kubernetes.Interface
	Informer  cache.SharedIndexInformer
}

// NewController creates a new controller
func NewController(clientset *kubernetes.Clientset) *Controller {
	factory := informers.NewSharedInformerFactory(clientset, 10*time.Minute)
	podInformer := factory.Core().V1().Pods().Informer()

	c := &Controller{
		Clientset: clientset,
		Informer:  podInformer,
	}

	podInformer.AddEventHandler(cache.ResourceEventHandlerFuncs{
		AddFunc:    c.onAdd,
		UpdateFunc: c.onUpdate,
	})

	return c
}

// Run starts the controller's informer
func (c *Controller) Run(stopCh <-chan struct{}) {
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
	// --- MODIFIED ---
	if isBad, reason := checkPodBadState(pod); isBad {
		log.Printf("TRIGGER: New pod %s/%s is in bad state: %s", pod.Namespace, pod.Name, reason)
		c.triggerAnalysis(pod, reason)
	}
}

// onUpdate is called when a pod is modified
func (c *Controller) onUpdate(oldObj, newObj interface{}) {
	oldPod := oldObj.(*corev1.Pod)
	newPod := newObj.(*corev1.Pod)

	// --- MODIFIED ---
	wasBad, _ := checkPodBadState(oldPod)
	isBad, reason := checkPodBadState(newPod)

	// Trigger only when transitioning from not-bad to bad
	if !wasBad && isBad {
		log.Printf("TRIGGER: Pod %s/%s has entered bad state: %s", newPod.Namespace, newPod.Name, reason)
		c.triggerAnalysis(newPod, reason)
	}
}

// --- NEW FUNCTION (Replaces isPodCrashLooping) ---
// checkPodBadState checks for various failure conditions.
// It returns true and a reason string if a failure state is detected.
func checkPodBadState(pod *corev1.Pod) (bool, string) {
	// 1. Check the overall Pod Phase
	if pod.Status.Phase == corev1.PodFailed {
		return true, "PodFailed"
	}

	// 2. Check Container Statuses
	for _, containerStatus := range pod.Status.ContainerStatuses {
		// Check for states like "CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull"
		if containerStatus.State.Waiting != nil {
			reason := containerStatus.State.Waiting.Reason
			if reason == "CrashLoopBackOff" || reason == "ImagePullBackOff" || reason == "ErrImagePull" {
				return true, reason
			}
		}

		// Check for containers that terminated with an "Error"
		if containerStatus.State.Terminated != nil {
			if containerStatus.State.Terminated.Reason == "Error" {
				return true, "Terminated(Error)"
			}
		}
	}

	return false, ""
}

// --- MODIFIED FUNCTION ---
// triggerAnalysis calls our Python AI agent service, now with a reason
func (c *Controller) triggerAnalysis(pod *corev1.Pod, reason string) {
	agentURL := "http://localhost:8000/summarize-pod"

	log.Printf("Triggering analysis for pod: %s/%s (Reason: %s)", pod.Namespace, pod.Name, reason)

	// 1. Create the JSON payload
	// --- MODIFIED: Added "reason" to payload ---
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

	// 2. Send the HTTP POST request
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

	// 3. Log the response
	if resp.StatusCode != http.StatusOK {
		log.Printf("ERROR: Agent service returned non-200 status: %s", resp.Status)
		// We can read the body here for more error details
		body, _ := io.ReadAll(resp.Body)
		log.Printf("Agent error response: %s", string(body))
		return
	}

	log.Printf("Successfully triggered analysis for %s/%s. Agent responded: %s", pod.Namespace, pod.Name, resp.Status)
}
