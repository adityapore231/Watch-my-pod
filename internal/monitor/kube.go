package monitor

import (
	"log"
	"os"
	"path/filepath"

	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
	"k8s.io/client-go/util/homedir"
)

// NewClientset creates and returns a new Kubernetes clientset.
// It searches for a config file in the following priority:
// 1. ./configs/kubeconfig
// 2. KUBECONFIG environment variable
// 3. ~/.kube/config
// 4. In-cluster service account
func NewClientset() (*kubernetes.Clientset, error) {
	var config *rest.Config
	var err error
	var kubeconfig string

	// --- NEW LOGIC START ---
	// 1. Try to find a local 'configs/kubeconfig' file first
	localConfigPath := filepath.Join(".", "configs", "kubeconfig")
	if _, err = os.Stat(localConfigPath); err == nil {
		log.Println("Using local config file:", localConfigPath)
		kubeconfig = localConfigPath
	} else {
		// 2. If not found, check KUBECONFIG env var
		kubeconfig = os.Getenv("KUBECONFIG")
		if kubeconfig == "" {
			// 3. If env var not set, use default home directory
			if home := homedir.HomeDir(); home != "" {
				kubeconfig = filepath.Join(home, ".kube", "config")
			}
		}
	}
	// --- NEW LOGIC END ---

	// Check if we found any out-of-cluster config
	if _, err = os.Stat(kubeconfig); err == nil {
		// Use out-of-cluster config
		if os.Getenv("KUBECONFIG") != "" {
			log.Println("Using KUBECONFIG env var:", kubeconfig)
		} else if kubeconfig != localConfigPath {
			log.Println("Using default kubeconfig:", kubeconfig)
		}

		config, err = clientcmd.BuildConfigFromFlags("", kubeconfig)
		if err != nil {
			return nil, err
		}
	} else {
		// 4. Use in-cluster config
		log.Println("No local config found. Assuming in-cluster config.")
		config, err = rest.InClusterConfig()
		if err != nil {
			return nil, err
		}
	}

	// Create the clientset
	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		return nil, err
	}

	return clientset, nil
}
