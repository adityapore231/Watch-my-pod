package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/adityapore231/Watch-my-pod/internal/monitor"
)

func main() {
	// 1. Create the Kubernetes clientset
	clientset, err := monitor.NewClientset()
	if err != nil {
		log.Fatalf("Failed to create clientset: %v", err)
	}

	// 2. Create the controller
	controller := monitor.NewController(clientset)

	// 3. Set up a channel to handle OS shutdown signals
	stopCh := make(chan struct{})
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-sigCh
		log.Println("Shutdown signal received, stopping controller...")
		close(stopCh)
	}()

	// 4. Run the controller
	controller.Run(stopCh)
}
