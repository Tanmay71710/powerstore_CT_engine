from kubernetes import client, config
from kubernetes.client.rest import ApiException


class KubernetesApi(object):
    def __init__(self, kubeconfig_path='/home/public/qa_apps/kubernetes/kubeconfig', 
    context='isg-pse-sysqa-prd/api-common-prod-drm-k8s-cec-delllabs-net:6443/system:serviceaccount:isg-pse-sysqa-prd:sysqa-serviceaccount'):     
        # Load the Kubernetes/OpenShift configuration from the provided kubeconfig file
        """
        Func initialize class Kubernetes.

        :param kubeconfig_path: kubeconfig_path
        :type kubeconfig_path: str
        :param baseFolder: The path to the root directories that contains all the files needed for the K8S (ex:
                   yaml file, scripts)
        :type baseFolder: str
        :returns: none
        """
        kubeconfig_path = '/usr/src/app/ns5'
        print(kubeconfig_path)
        self.kubeconfig_path = kubeconfig_path
        self.namespace = 'isg-pse-sysqa-prd'
        config.load_kube_config(config_file=kubeconfig_path, context=context)
        self.api_instance = client.AppsV1Api()
        self.core_api_instance = client.CoreV1Api()
        self.networking_api_instance = client.NetworkingV1Api()
        self.ingress = None

    @property
    def ingress(self):
        """Getter for self.fru

        :parameter: none
        :return: M.2 FRU object
        :rtype: newFru.FruM2Drive
        """
        if self._ingress is None:
            self.ingress = self.check_and_create_ingress()
        return self._ingress

    @ingress.setter
    def ingress(self, value):
        """Setter for fru

            :param value: value to set
            :type value: str
            :return: None
        """
        self._ingress = value   # pylint: disable=attribute-defined-outside-init
     
    def create_deployment(self, app_name, app_port, test_set_name):
        # Define the deployment
        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=f"{app_name}-deployment"),
            spec=client.V1DeploymentSpec(
                replicas=1,
                selector=client.V1LabelSelector(
                    match_labels={"app": app_name}
                ),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels={"app": app_name}),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
                                name=f"{app_name}-container",
                                image="pstore.artifactory.cec.lab.emc.com/powerstore-ct-engine-sysqa:latest",
                                ports=[client.V1ContainerPort(container_port=app_port)],
                                command=["/usr/local/bin/python"],
                                args=[
                                    "execution_engine/app.py",
                                    "--port", str(app_port),
                                    "--test_set_name", test_set_name
                                ],
                                env=[
                                    client.V1EnvVar(name="APP_PORT", value=str(app_port)),
                                    client.V1EnvVar(name="TEST_SET_NAME", value=test_set_name)
                                ],
                                volume_mounts=[
                                    client.V1VolumeMount(
                                        name="nfs-storage",
                                        mount_path="/home/"
                                    )
                                ]
                            )
                        ],
                        volumes=[
                            client.V1Volume(
                                name="nfs-storage",
                                persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                                    claim_name="trident-pvc"
                                )
                            )
                        ]
                    )
                )
            )
        )

        # Create the deployment
        self.api_instance.create_namespaced_deployment(
            namespace=self.namespace, body=deployment
        )
        print(f"Deployment {app_name} created successfully.")
    
    def create_service(self, app_name, port):
        res = None
        service = client.V1Service(
            api_version='v1',
            kind='Service',
            metadata=client.V1ObjectMeta(name=f'{app_name}-service'),
            spec=client.V1ServiceSpec(
                selector={'app': app_name},
                ports=[client.V1ServicePort(port=port, target_port=port)],
                type='LoadBalancer'
            )
        )
        res = self.core_api_instance.create_namespaced_service(namespace=self.namespace, body=service)
        print(f"Service for {app_name} created successfully")
        return res
    
    def create_ingress(self):
        ingress = client.V1Ingress(
            api_version='networking.k8s.io/v1',
            kind='Ingress',
            metadata=client.V1ObjectMeta(name='app-ingress', namespace=self.namespace),
            spec=client.V1IngressSpec(
                rules=[
                    client.V1IngressRule(
                        host="",  # Replace with your domain
                        http=client.V1HTTPIngressRuleValue(
                            paths=[
                                client.V1HTTPIngressPath(
                                    path='/',
                                    path_type='Prefix',
                                    backend=client.V1IngressBackend(
                                        service=client.V1IngressServiceBackend(
                                            name='app1-service',  # Replace with your service name
                                            port=client.V1ServiceBackendPort(number=80)  # Replace with your service port
                                        )
                                    )
                                )
                            ]
                        )
                    )
                ]
            )
        )
        
        try:
            self.networking_api_instance.create_namespaced_ingress(namespace=self.namespace, body=ingress)
            print("Ingress created successfully")
        except ApiException as e:
            print(f"Exception when creating Ingress: {e}")

    def check_and_create_ingress(self):
        ingress = None
        try:
            ingress = self.networking_api_instance.read_namespaced_ingress(name='app-ingress', namespace=self.namespace)
            print("Ingress already exists")
        except ApiException as e:
            if e.status == 404:
                print("Ingress not found, creating...")
                self.create_ingress()
                ingress = self.networking_api_instance.read_namespaced_ingress(name='app-ingress', namespace=self.namespace)
            else:
                print(f"Exception when checking Ingress: {e}")
        return ingress

    def update_ingress(self, ingress):
        try:
            self.networking_api_instance.replace_namespaced_ingress(name='app-ingress', namespace=self.namespace, body=ingress)
            print("Ingress updated successfully")
        except ApiException as e:
            print(f"Exception when updating Ingress: {e}")
    
    def add_app2_path(self, ingress, app_name, port):
        # Access the paths in the Ingress rule
        paths = ingress.spec.rules[0].http.paths if ingress.spec.rules[0].http.paths else []

        # Check if the path already exists
        if any(p.path == f"/{app_name}" for p in paths):
            print(f"Path /{app_name} already exists in Ingress")
            return

        # Append the new path
        paths.append(
            client.V1HTTPIngressPath(  # Make sure the class name is correct
                path=f'/{app_name}',
                path_type='Prefix',
                backend=client.V1IngressBackend(  # Use V1IngressBackend
                    service=client.V1IngressServiceBackend(  # Use V1IngressServiceBackend
                        name=f'{app_name}-service',
                        port=client.V1ServiceBackendPort(number=port)  # Use V1ServiceBackendPort
                    )
                )
            )
        )

        # Update the Ingress paths
        ingress.spec.rules[0].http.paths = paths
        self.update_ingress(ingress)

    def delete_deployment(self, app_name):
        try:
            self.api_instance.delete_namespaced_deployment(name=f'{app_name}-deployment', namespace=self.namespace)
            print(f"Deployment for {app_name} deleted successfully")
        except ApiException as e:
            print(f"Exception when deleting Deployment: {e}")

    def delete_service(self, app_name):
        try:
            self.core_api_instance.delete_namespaced_service(name=f'{app_name}-service', namespace=self.namespace)
            print(f"Service for {app_name} deleted successfully")
        except ApiException as e:
            print(f"Exception when deleting Service: {e}")

    def remove_app2_path(self, ingress, app_name):
        paths = [p for p in ingress.spec.rules[0].http.paths if p.path != f"/{app_name}"]
        if len(paths) == len(ingress.spec.rules[0].http.paths):
            print(f"Path /{app_name} does not exist in Ingress")
            return

        ingress.spec.rules[0].http.paths = paths
        self.update_ingress(ingress)

    def get_used_ports(self):
        try:
            services = self.core_api_instance.list_namespaced_service(namespace=self.namespace)
            used_ports = set()
            
            for service in services.items:
                for port in service.spec.ports:
                    used_ports.add(port.port)
            
            return used_ports
        except ApiException as e:
            print(f"Exception when retrieving services: {e}")
            return set()

    def find_next_unused_port(self, start_port=5005, end_port=9000):
        used_ports = self.get_used_ports()
        for port in range(start_port, end_port + 1):
            if port not in used_ports:
                return port
        print("No available ports in the specified range.")
        return None

    def get_load_balancer_info(self, app_name):

        service_name = f'{app_name}-service'
        service = self.core_api_instance.read_namespaced_service(service_name, self.namespace)

        # Check if the service type is LoadBalancer
        if service.spec.type != 'LoadBalancer':
            print(f"Service {service_name} is not of type 'LoadBalancer'")
            raise KeyError(f'{service_name} is not LoadBalancer')

        # Retrieve load balancer details
        for ingress in (service.status.load_balancer.ingress or []):
            ip = ingress.ip if ingress.ip else ingress.hostname
            ports = next(port.port for port in service.spec.ports)
            return ip, ports
        raise KeyError(f'No info for {service_name}')

# def main():
#     ingress = networking_api_instance.read_namespaced_ingress(name='app-ingress', namespace=namespace)
#     if ingress:
#         app_name = 'app2-new'
#         port = 8081
#         create_deployment(app_name, port)
#         create_service(app_name, port)
#         add_app2_path(ingress, app_name, port)


# def main():
#     ingress = networking_api_instance.read_namespaced_ingress(name='app-ingress', namespace=namespace)
#     if ingress:
#         app_name = 'app2-to-remove'
#         delete_deployment(app_name)
#         delete_service(app_name)
#         remove_app2_path(ingress, app_name)
