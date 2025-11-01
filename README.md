# Watch-My-Pod: AI-Powered Kubernetes Pod Failure Analysis

Watch-My-Pod is an automated monitoring and analysis tool for Kubernetes. It actively watches for pod failures (like `CrashLoopBackOff`, `ImagePullBackOff`, etc.), collects relevant diagnostic data, uses a Generative AI agent to perform a root cause analysis, and provides a clear, concise summary suitable for developers.

This system helps SREs and developers reduce the mean time to resolution (MTTR) by automating the initial, time-consuming investigation steps of a pod failure.

## Features

- **Real-time Monitoring**: A Go-based controller watches the Kubernetes API for pod failure events.
- **Automated Data Collection**: When a failing pod is detected, a Python service agent collects its logs and events.
- **AI-Powered Analysis**: The collected data is sent to a Google Gemini-powered AI agent, which analyzes the information and generates a human-readable summary of the likely root cause.
- **Microservice Architecture**: The system is composed of two main services:
    1.  **Go Monitor**: A lightweight Kubernetes controller that detects failures.
    2.  **Python Service Agent**: A FastAPI-based web service that handles data collection and AI analysis.
- **Easy Deployment**: The entire system can be deployed into a Kubernetes cluster using the provided manifests.

## Architecture

The workflow is simple and effective:

1.  The **Go Monitor** watches for pod status changes in the cluster.
2.  When it detects a pod in a failing state (e.g., `CrashLoopBackOff`), it sends the pod's namespace and name to the **Python Service Agent**.
3.  The Service Agent's **Collector** module uses the Kubernetes API to gather the pod's logs and recent events.
4.  The collected data is passed to the **AI Agent** (powered by LangGraph and Google Gemini), which analyzes the context and produces a summary.
5.  The summary is logged, and (in a future implementation) can be sent to an alerting platform like Slack.

```
+-------------------+      +----------------------+      +-----------------------+
| Kubernetes Cluster|      |      Go Monitor      |      | Python Service Agent  |
| (Failing Pod)     |----->|  (Detects Failure)   |----->| (Receives Request)    |
+-------------------+      +----------------------+      +-----------------------+
                                                                   |
                                                                   | (Collects Data)
                                                                   v
                                                     +--------------------------+
                                                     |  AI Agent (Gemini)       |
                                                     |  (Analyzes & Summarizes) |
                                                     +--------------------------+
                                                                   |
                                                                   v
                                                         +--------------------+
                                                         |  Developer / Slack |
                                                         +--------------------+
```

## Prerequisites

Before you begin, ensure you have the following installed:

- **Go** (version 1.18+)
- **Python** (version 3.9+)
- **Docker** & **Docker Desktop** (or another container runtime)
- **kubectl**
- **A Kubernetes Cluster**: You can use a local cluster like [Minikube](https://minikube.sigs.k8s.io/docs/start/), [Kind](https://kind.sigs.k8s.io/docs/user/quick-start/), or the one included with Docker Desktop.

## Setup & Installation

### 1. Clone the Repository

```sh
git clone https://github.com/adityapore231/Watch-my-pod.git
cd Watch-my-pod
```

### 2. Configure the AI Agent

The Python Service Agent uses the Google Gemini API. You'll need to provide an API key.

-   Navigate to the `service-agent` directory:
    ```sh
    cd service-agent
    ```
-   Create a file named `.env`:
    ```sh
    touch .env
    ```
-   Add your Google API key to the `.env` file:
    ```
    # .env file
    GOOGLE_API_KEY="your-google-api-key-here"
    ```

### 3. Build and Deploy the Services

The easiest way to run the system is to deploy it directly into your Kubernetes cluster.

-   **Enable Ingress on Minikube (if using Minikube)**
    If you are using Minikube, you need to enable the ingress controller:
    ```sh
    minikube addons enable ingress
    ```

-   **Build the Docker Images**
    Make sure your Docker daemon is running. Use the following commands from the root of the project to build the images and load them into your local cluster's registry.

    For Minikube:
    ```sh
    # Point your local Docker daemon to Minikube's registry
    eval $(minikube -p minikube docker-env)

    # Build the images
    docker build -t watch-my-pod-monitor:latest -f build/monitor/Dockerfile .
    docker build -t watch-my-pod-service-agent:latest -f service-agent/Dockerfile .
    ```

    For other cluster types, you may need to push the images to a container registry (like Docker Hub, GCR, or ECR) and update the `image` fields in `configs/deployment.yaml`.

-   **Deploy to Kubernetes**
    From the root of the project, apply the Kubernetes manifests:
    ```sh
    kubectl apply -k ./configs
    ```
    This will create the necessary `ClusterRole`, `ClusterRoleBinding`, and `Deployments` for both services.

## Usage

Once deployed, Watch-My-Pod runs automatically.

-   The **Go monitor** will immediately start watching for pod failures across all namespaces.
-   To test it, you can deploy a pod that is designed to fail. For example, a pod with a command that exits with an error, causing a `CrashLoopBackOff`.
-   When a failure is detected, you can view the logs from the service agent to see the collected data and the AI-generated summary.

To see the logs from the service agent:

```sh
# Find the service-agent pod name
kubectl get pods -n watch-my-pod-system

# Stream the logs
kubectl logs -f <your-service-agent-pod-name> -n watch-my-pod-system
```

You should see output detailing the event reception, data collection, and the final AI summary.

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.
