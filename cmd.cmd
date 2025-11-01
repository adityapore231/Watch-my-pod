kubectl run crasher --image=busybox -- /bin/sh -c "exit 1"
kubectl run java-crash --image=openjdk:17-jdk --restart=Never -- java -jar /nonexistent/app.jar