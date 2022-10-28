# Create cicd_bw_k8s network
resource "ovh_cloud_project_network_private" "network" {
  provider = ovh.ovh
  name = "cicd_bw_k8s"
  regions = ["SBG5"]
  vlan_id = 60
}
resource "ovh_cloud_project_network_private_subnet" "subnet" {
  provider = ovh.ovh
  depends_on = [ovh_cloud_project_network_private.network]
  network_id = ovh_cloud_project_network_private.network.id
  start = "192.168.42.100"
  end = "192.168.42.200"
  network = "192.168.42.0/24"
  region = "SBG5"
  dhcp = true
  no_gateway = false
}

# Create k8s cluster
resource "ovh_cloud_project_kube" "cluster" {
  provider = ovh.ovh
  depends_on = [ovh_cloud_project_network_private_subnet.subnet]
  name = "cicd_bw_k8s"
  region = "SBG5"
  version = "1.24"
  private_network_id = tolist(ovh_cloud_project_network_private.network.regions_attributes[*].openstackid)[0]
  private_network_configuration {
    default_vrack_gateway = ""
    private_network_routing_as_default = false
  }
}

# Create nodepool
resource "ovh_cloud_project_kube_nodepool" "pool" {
  provider = ovh.ovh
  kube_id = ovh_cloud_project_kube.cluster.id
  name = "pool"
  flavor_name = "d2-4"
  desired_nodes = 3
  min_nodes = 3
  max_nodes = 3
  monthly_billed = false
  autoscale = false
}

# Get kubeconfig file
resource "local_file" "kubeconfig" {
  content = ovh_cloud_project_kube.cluster.kubeconfig
  filename = "/tmp/kubeconfig"  
}
