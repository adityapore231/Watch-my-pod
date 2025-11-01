package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/adityapore231/Watch-my-pod/internal/monitor"
)

func main() {
	log.Println("Starting Watch-my-pod monitor...")

	// Initialize Kubernetes client
	clientset, err := monitor.GetKubernetesClient()
	if err != nil {
		log.Fatalf("Failed to create Kubernetes client: %v", err)
	}

	// Create and start the controller
	controller := monitor.NewController(clientset)
	stopCh := make(chan struct{})
	defer close(stopCh)

	go controller.Run(stopCh)

	// Wait for interrupt signal to gracefully shutdown
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	log.Println("Shutting down Watch-my-pod monitor...")
}
