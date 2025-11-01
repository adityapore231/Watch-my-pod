package monitor

import (
	"log"
	"time"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/util/runtime"
	"k8s.io/apimachinery/pkg/util/wait"
	"k8s.io/client-go/informers"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/tools/cache"
	"k8s.io/client-go/util/workqueue"
)

// Controller watches for pod events in the Kubernetes cluster
type Controller struct {
	clientset      *kubernetes.Clientset
	informerFactory informers.SharedInformerFactory
	podInformer    cache.SharedIndexInformer
	queue          workqueue.RateLimitingInterface
}

// NewController creates a new Controller instance
func NewController(clientset *kubernetes.Clientset) *Controller {
	informerFactory := informers.NewSharedInformerFactory(clientset, time.Minute*5)
	podInformer := informerFactory.Core().V1().Pods().Informer()

	queue := workqueue.NewRateLimitingQueue(workqueue.DefaultControllerRateLimiter())

	controller := &Controller{
		clientset:      clientset,
		informerFactory: informerFactory,
		podInformer:    podInformer,
		queue:          queue,
	}

	// Add event handlers
	podInformer.AddEventHandler(cache.ResourceEventHandlerFuncs{
		AddFunc:    controller.handleAdd,
		UpdateFunc: controller.handleUpdate,
		DeleteFunc: controller.handleDelete,
	})

	return controller
}

// Run starts the controller
func (c *Controller) Run(stopCh <-chan struct{}) {
	defer runtime.HandleCrash()
	defer c.queue.ShutDown()

	log.Println("Starting controller...")

	c.informerFactory.Start(stopCh)

	if !cache.WaitForCacheSync(stopCh, c.podInformer.HasSynced) {
		runtime.HandleError(nil)
		return
	}

	log.Println("Controller synced and ready")

	wait.Until(c.runWorker, time.Second, stopCh)
}

func (c *Controller) runWorker() {
	for c.processNextItem() {
	}
}

func (c *Controller) processNextItem() bool {
	key, quit := c.queue.Get()
	if quit {
		return false
	}
	defer c.queue.Done(key)

	err := c.processItem(key.(string))
	if err == nil {
		c.queue.Forget(key)
	} else {
		runtime.HandleError(err)
		c.queue.AddRateLimited(key)
	}

	return true
}

func (c *Controller) processItem(key string) error {
	log.Printf("Processing item: %s", key)
	// TODO: Implement actual processing logic
	// This would typically involve fetching the pod details and triggering the AI agent
	return nil
}

func (c *Controller) handleAdd(obj interface{}) {
	pod := obj.(*corev1.Pod)
	log.Printf("Pod added: %s/%s", pod.Namespace, pod.Name)
	key, err := cache.MetaNamespaceKeyFunc(obj)
	if err == nil {
		c.queue.Add(key)
	}
}

func (c *Controller) handleUpdate(oldObj, newObj interface{}) {
	oldPod := oldObj.(*corev1.Pod)
	newPod := newObj.(*corev1.Pod)
	
	if oldPod.Status.Phase != newPod.Status.Phase {
		log.Printf("Pod updated: %s/%s, Phase: %s -> %s", 
			newPod.Namespace, newPod.Name, oldPod.Status.Phase, newPod.Status.Phase)
		key, err := cache.MetaNamespaceKeyFunc(newObj)
		if err == nil {
			c.queue.Add(key)
		}
	}
}

func (c *Controller) handleDelete(obj interface{}) {
	pod := obj.(*corev1.Pod)
	log.Printf("Pod deleted: %s/%s", pod.Namespace, pod.Name)
	key, err := cache.MetaNamespaceKeyFunc(obj)
	if err == nil {
		c.queue.Add(key)
	}
}
