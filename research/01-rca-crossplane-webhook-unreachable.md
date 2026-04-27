# RCA — Crossplane webhook unreachable

## Observed defect

During INIT-119 local full-stack bring-up, Flux reconciliation of the app-cluster API layer fails when Kubernetes admission calls Crossplane's validating webhooks.

```text
$ kubectl --kubeconfig ~/.kube/humility-local.yaml get kustomizations.kustomize.toolkit.fluxcd.io -A -o wide
NAMESPACE     NAME                               READY   STATUS
flux-system   humility-local-app-cluster-api     False   Composition/appcluster-k3d-local dry-run failed (InternalError): Internal error occurred: failed calling webhook "compositions.apiextensions.crossplane.io": failed to call webhook: Post "https://crossplane-webhooks.crossplane-system.svc:9443/validate-apiextensions-crossplane-io-v1-composition?timeout=10s": proxy error from 127.0.0.1:6443 while dialing 10.42.0.18:9443, code 502: 502 Bad Gateway...
```

```text
$ kubectl --kubeconfig ~/.kube/humility-local.yaml get events -A --sort-by=.lastTimestamp | rg -i 'crossplane|webhook|bad gateway|10\.42\.0\.18'
flux-system Warning ReconciliationFailed kustomization/humility-local-app-cluster-api
  CompositeResourceDefinition/xappclusters.platform.humility.gg dry-run failed ... failed calling webhook "compositeresourcedefinitions.apiextensions.crossplane.io" ... proxy error from 127.0.0.1:6443 while dialing 10.42.0.18:9443, code 502: 502 Bad Gateway
flux-system Warning ReconciliationFailed kustomization/humility-local-app-cluster-api
  Composition/appcluster-k3d-local dry-run failed ... failed calling webhook "compositions.apiextensions.crossplane.io" ... proxy error from 127.0.0.1:6443 while dialing 10.42.0.18:9443, code 502: 502 Bad Gateway
```

Crossplane is Ready and the webhook Service resolves to the expected endpoint:

```text
$ kubectl --kubeconfig ~/.kube/humility-local.yaml get pods -n crossplane-system -o wide
NAME                                      READY   STATUS    RESTARTS   IP           NODE
crossplane-7bd959bf7b-jqdn7              1/1     Running   0          10.42.0.18   k3d-humility-local-agent-0
crossplane-rbac-manager-5b85878d44-58c7l 1/1     Running   0          10.42.1.23   k3d-humility-local-server-0

$ kubectl --kubeconfig ~/.kube/humility-local.yaml get svc,endpoints,endpointslice -n crossplane-system -o wide
service/crossplane-webhooks   ClusterIP   10.43.148.32   9443/TCP   app=crossplane,release=crossplane
endpoints/crossplane-webhooks                         10.42.0.18:9443
endpointslice.discovery.k8s.io/crossplane-webhooks-b4m6p   10.42.0.18
```

Same-namespace pod-to-pod traffic also fails, including from the same node as Crossplane after waiting for policy state to settle:

```text
$ kubectl --kubeconfig ~/.kube/humility-local.yaml run rca-crossplane-netcheck-wait --rm -i --restart=Never -n crossplane-system --image=curlimages/curl:8.16.0 --overrides='{"apiVersion":"v1","spec":{"nodeName":"k3d-humility-local-agent-0"}}' --command -- sh -c 'sleep 8; ip route; for u in http://10.42.0.18:8081/readyz https://10.42.0.18:9443/healthz https://crossplane-webhooks.crossplane-system.svc:9443/healthz; do echo URL=$u; curl -skm 5 -w " HTTP_STATUS=%{http_code} EXIT=%{exitcode}\n" -o /tmp/out "$u"; cat /tmp/out 2>/dev/null || true; echo; done'
default via 10.42.0.1 dev eth0
10.42.0.0/24 dev eth0 scope link  src 10.42.0.44
URL=http://10.42.0.18:8081/readyz
 HTTP_STATUS=000 EXIT=7
URL=https://10.42.0.18:9443/healthz
 HTTP_STATUS=000 EXIT=7
URL=https://crossplane-webhooks.crossplane-system.svc:9443/healthz
 HTTP_STATUS=000 EXIT=7
pod "rca-crossplane-netcheck-wait" deleted from crossplane-system namespace
```

## Intended behavior

Kubernetes dynamic admission should call the webhook service named in the `ValidatingWebhookConfiguration`. Kubernetes admission docs state that an in-cluster webhook is commonly deployed behind a Service, and when a request matches a webhook rule the API server sends an `AdmissionReview` to the configured `clientConfig`. Source: Kubernetes dynamic admission docs, <https://v1-33.docs.kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/>.

```text
External source excerpts:
Kubernetes admission docs L842-L845: webhook server deployed in cluster; Service created as front-end.
Kubernetes admission docs L864-L868: ValidatingWebhookConfiguration clientConfig.service namespace/name.
Kubernetes admission docs L880: server cert must be valid for <svc_name>.<svc_namespace>.svc.
Kubernetes admission docs L883-L885: default timeout is 10s; matching requests are sent to clientConfig.
```

Crossplane v1.20 documents that its init container configures Crossplane webhooks and its core container processes webhooks. Source: Crossplane v1.20 pod docs, <https://docs.crossplane.io/v1.20/concepts/pods/>.

```text
External source excerpts:
Crossplane docs L149: base install includes crossplane and crossplane-rbac-manager pods.
Crossplane docs L153-L158: init container installs core CRDs and configures webhooks.
Crossplane docs L180-L183: main Crossplane container processes webhooks.
```

The rendered Crossplane manifest matches that contract: `crossplane-webhooks` selects `app=crossplane,release=crossplane`, exposes Service port `9443` to targetPort `9443`, sets `WEBHOOK_SERVICE_PORT=9443`, and declares container ports `8081` (`readyz`) and `9443` (`webhooks`).

```text
$ rg -n 'name: crossplane-webhooks|WEBHOOK_SERVICE_PORT|containerPort: 8081|containerPort: 9443|targetPort: 9443' gitops/channels/local/app-clusters/crossplane/core/rendered/crossplane-1.20.7.yaml
659:  name: crossplane-webhooks
679:    targetPort: 9443
766:          - name: "WEBHOOK_SERVICE_PORT"
795:          containerPort: 8081
797:          containerPort: 9443
```

NetworkPolicy intended behavior is central here. Kubernetes docs say pods are non-isolated by default, but any ingress NetworkPolicy selecting a pod makes that pod ingress-isolated. Once isolated, only traffic from the pod's node plus traffic allowed by selected ingress policies may enter; pod-to-pod traffic also requires source egress and destination ingress to allow the connection. Source: Kubernetes NetworkPolicy docs, <https://v1-33.docs.kubernetes.io/docs/concepts/services-networking/network-policies/>.

```text
External source excerpts:
Kubernetes NetworkPolicy docs L836: NetworkPolicy requires a plugin that implements it.
Kubernetes NetworkPolicy docs L840-L845: default non-isolated; selecting ingress policy isolates ingress; allowed connections are additive; both egress and ingress matter.
Kubernetes NetworkPolicy docs L842: isolated pods allow traffic from the pod's node and allowed ingress rules.
```

K3s provides the NetworkPolicy implementation and the relevant k3d cluster uses the default Flannel model. Sources: K3s networking services, <https://docs.k3s.io/networking/networking-services>, and K3s basic network options, <https://docs.k3s.io/networking/basic-network-options>.

```text
External source excerpts:
K3s networking services L73-L80: embedded kube-router netpol controller; KUBE-ROUTER iptables rules.
K3s basic network options L59-L63: Flannel vxlan is the default backend unless another backend is selected.
K3s basic network options L133-L142: agents and servers maintain websocket tunnels; default egress selector mode is agent; pod/cluster modes route service endpoint connections over tunnels.
```

## Failure path trace

1. Flux dry-runs Crossplane `CompositeResourceDefinition` and `Composition` resources.
2. The API server admission dispatcher matches Crossplane validating webhook rules.
3. The webhook `clientConfig.service` resolves to endpoint `10.42.0.18:9443`.
4. In this k3s/k3d topology, the API server path to the endpoint goes through k3s' local tunnel/proxy path; the 502 is generated while that proxy dials the endpoint.
5. The destination node's kube-router NetworkPolicy chain rejects unmatched traffic to the Crossplane pod before the Crossplane process receives it.
6. Kubelet readiness still succeeds because node-local traffic to the pod is allowed by NetworkPolicy semantics and by the live kube-router rule.

Webhook configuration:

```text
$ kubectl --kubeconfig ~/.kube/humility-local.yaml get validatingwebhookconfiguration crossplane -o yaml
webhooks:
- name: compositeresourcedefinitions.apiextensions.crossplane.io
  clientConfig:
    service:
      name: crossplane-webhooks
      namespace: crossplane-system
      path: /validate-apiextensions-crossplane-io-v1-compositeresourcedefinition
      port: 9443
  failurePolicy: Fail
- name: compositions.apiextensions.crossplane.io
  clientConfig:
    service:
      name: crossplane-webhooks
      namespace: crossplane-system
      path: /validate-apiextensions-crossplane-io-v1-composition
      port: 9443
  failurePolicy: Fail
```

API server / k3s proxy evidence:

```text
$ docker logs --since=2h k3d-humility-local-server-0 2>&1 | grep -iE '10\.42\.0\.18|crossplane|webhook|Bad Gateway' | tail -20
time="2026-04-27T20:11:32Z" level=error msg="Sending HTTP/1.1 502 response to 127.0.0.1:37950: dial tcp 10.42.0.18:9443: connect: connection refused"
W0427 20:11:32.635943 76 dispatcher.go:217] Failed calling webhook, failing closed compositeresourcedefinitions.apiextensions.crossplane.io ... proxy error from 127.0.0.1:6443 while dialing 10.42.0.18:9443, code 502: 502 Bad Gateway
W0427 20:11:47.780742 76 dispatcher.go:217] Failed calling webhook, failing closed compositions.apiextensions.crossplane.io ... proxy error from 127.0.0.1:6443 while dialing 10.42.0.18:9443, code 502: 502 Bad Gateway
```

The API aggregation layer itself is ready; this is admission webhook dispatch, not a general aggregator outage. Evidence: `kubectl --kubeconfig ~/.kube/humility-local.yaml get --raw /readyz?verbose` reports `poststarthook/start-kube-aggregator-informers ok`, `apiservice-status-remote-available-controller ok`, and `readyz check passed`.

k3d/k3s network model:

```text
$ k3d cluster get humility-local -o yaml
network: {isExternal: true, name: k3d-humility-local}
nodes:
- {name: k3d-humility-local-server-0, IP: 172.28.0.3, role: server}
- {name: k3d-humility-local-agent-0, IP: 172.28.0.4, role: agent}
serverLoadBalancer: {name: k3d-humility-local-serverlb, IP: 172.28.0.5}

$ docker exec k3d-humility-local-server-0 ip route && docker exec k3d-humility-local-agent-0 ip route
server: 10.42.0.0/24 via 10.42.0.0 dev flannel.1 onlink
server: 10.42.1.0/24 dev cni0 proto kernel scope link src 10.42.1.1
agent:  10.42.0.0/24 dev cni0 proto kernel scope link src 10.42.0.1
agent:  10.42.1.0/24 via 10.42.1.0 dev flannel.1 onlink

$ docker logs --since=2h k3d-humility-local-agent-0 2>&1 | grep -iE 'flannel|network policy controller' | head
I0427 18:26:59.029817 76 vxlan_network.go:68] watching for new subnet leases
I0427 18:27:04.122361 76 network_policy_controller.go:164] Starting network policy controller
```

Service DNAT exists:

```text
$ docker exec k3d-humility-local-agent-0 sh -lc 'iptables-save | grep -n "crossplane-system/crossplane-webhooks" | head -20'
975:-A KUBE-SEP-CAZEQ5TIED6R5LRY ... -j DNAT --to-destination 10.42.0.18:9443
1058:-A KUBE-SERVICES -d 10.43.148.32/32 ... "crossplane-system/crossplane-webhooks cluster IP" ... --dport 9443 -j KUBE-SVC-DHTL2O3DQ6VPFDHS
1132:-A KUBE-SVC-DHTL2O3DQ6VPFDHS ... "crossplane-system/crossplane-webhooks -> 10.42.0.18:9443" -j KUBE-SEP-CAZEQ5TIED6R5LRY
```

## Evidence

Crossplane startup completed and generated webhook configuration:

```text
$ kubectl --kubeconfig ~/.kube/humility-local.yaml logs -n crossplane-system crossplane-7bd959bf7b-jqdn7 -c crossplane-init
{"ts":"2026-04-27T18:35:34Z","msg":"TLS CA secret is complete.","Step":"TLSCertificateGenerator"}
{"ts":"2026-04-27T18:35:35Z","msg":"Step has been completed","Name":"WebhookConfigurations"}
{"ts":"2026-04-27T18:35:35Z","msg":"Initialization has been completed"}

$ kubectl --kubeconfig ~/.kube/humility-local.yaml describe pod -n crossplane-system crossplane-7bd959bf7b-jqdn7
Ports: 8081/TCP (readyz), 9443/TCP (webhooks)
State: Running
Ready: True
Restart Count: 0
Startup: tcp-socket :readyz delay=0s timeout=1s period=2s #failure=30
Events: <none>
```

The listener is not loopback-only:

```text
$ docker exec k3d-humility-local-agent-0 sh -lc 'awk "NR==1 || /:1F91|:24E3/" /proc/13407/net/tcp6'
sl  local_address                         remote_address                        st uid
1: 00000000000000000000000000000000:1F91 00000000000000000000000000000000:0000 0A 65532
2: 00000000000000000000000000000000:24E3 00000000000000000000000000000000:0000 0A 65532
```

`1F91` is 8081, `24E3` is 9443, `st 0A` is LISTEN, and the all-zero bind address plus allowed-namespace access weighs against 127.0.0.1-only binding. Node-local readiness works:

```text
$ docker exec k3d-humility-local-agent-0 sh -lc 'timeout 5 wget -S -O- --no-check-certificate http://10.42.0.18:8081/readyz 2>&1 | head -20'
Connecting to 10.42.0.18:8081 (10.42.0.18:8081)
  HTTP/1.1 200 OK
ok
```

The live NetworkPolicy selects all Crossplane pods and allows only observability ingress:

```text
$ kubectl --kubeconfig ~/.kube/humility-local.yaml get networkpolicy -n crossplane-system -o wide
NAMESPACE           NAME                         POD-SELECTOR   AGE
crossplane-system   allow-observability-scrape   <none>         94m

$ kubectl --kubeconfig ~/.kube/humility-local.yaml describe networkpolicy -n crossplane-system allow-observability-scrape
PodSelector: <none> (Allowing the specific traffic to all pods in this namespace)
Allowing ingress traffic:
  To Port: <any>
  From:
    NamespaceSelector: kubernetes.io/metadata.name=observability-system
Not affecting egress traffic
Policy Types: Ingress
```

kube-router rules enforce that policy and reject unmatched traffic to Crossplane:

```text
$ docker exec k3d-humility-local-agent-0 sh -lc 'iptables-save | grep -nE "allow-observability-scrape namespace crossplane-system|10\\.42\\.0\\.18|POD name:crossplane" | head -30'
150:-A KUBE-NWPLCY-27PZW5T2SWOKMJNB ... "rule to ACCEPT traffic from source pods to dest pods selected by policy name allow-observability-scrape namespace crossplane-system" ...
152:-A KUBE-NWPLCY-27PZW5T2SWOKMJNB ... --nflog-prefix "DROP by policy crossplane-system/allow-observability-scrape"
603:-A KUBE-POD-FW-O3VTVHJARZV24UFD -d 10.42.0.18/32 ... "rule to permit the traffic traffic to pods when source is the pod's local node" ... -j ACCEPT
605:-A KUBE-POD-FW-O3VTVHJARZV24UFD -d 10.42.0.18/32 ... "run through nw policy allow-observability-scrape" -j KUBE-NWPLCY-27PZW5T2SWOKMJNB
607:-A KUBE-POD-FW-O3VTVHJARZV24UFD ... "rule to REJECT traffic destined for POD name:crossplane-7bd959bf7b-jqdn7 namespace: crossplane-system" ... -j REJECT --reject-with icmp-port-unreachable
```

An allowed namespace can reach the listeners after policy state settles:

```text
$ kubectl --kubeconfig ~/.kube/humility-local.yaml run rca-obs-netcheck-wait --rm -i --restart=Never -n observability-system --image=curlimages/curl:8.16.0 --command -- sh -c 'sleep 8; for u in http://10.42.0.18:8081/readyz https://10.42.0.18:9443/healthz; do echo URL=$u; curl -skm 5 -w " HTTP_STATUS=%{http_code} EXIT=%{exitcode}\n" -o /tmp/out "$u"; cat /tmp/out 2>/dev/null || true; echo; done'
URL=http://10.42.0.18:8081/readyz
 HTTP_STATUS=200 EXIT=0
ok
URL=https://10.42.0.18:9443/healthz
 HTTP_STATUS=404 EXIT=0
404 page not found
pod "rca-obs-netcheck-wait" deleted from observability-system namespace
```

The 404 on 9443 means the TLS/HTTP connection reached the webhook listener even though `/healthz` is not a valid webhook-port endpoint.

Git history:

```text
$ git log --oneline -- gitops/channels/local/app-clusters/crossplane/ gitops/channels/local/security/ | head -6
a82d5be feat: SLICE-107.03 network policy isolation
5ce0b79 feat: SLICE-107.02 security channel contract and PSS labels
70bc272 feat: SLICE-106.02 Crossplane core and providers
$ git show --name-status --format='%h %ad %s' --date=short 70bc272 -- gitops/channels/local/app-clusters/crossplane | head
70bc272 2026-04-26 feat: SLICE-106.02 Crossplane core and providers
A gitops/channels/local/app-clusters/crossplane/core/rendered/crossplane-1.20.7.yaml
```

INIT-107 does not add a `crossplane-system` default-deny in the reviewed file:

```text
$ sed -n '1,80p' gitops/channels/local/security/restricted-default-deny.yaml
metadata: {name: default-deny, namespace: cert-manager-test}
metadata: {name: default-deny, namespace: humility-gitops-sentinel}
metadata: {name: default-deny, namespace: infisical-system}
metadata: {name: default-deny, namespace: minio-system}
```

The all-pods Crossplane scrape policy comes from INIT-117 observability work:

```text
$ git log --oneline -- gitops/channels/local/observability/networkpolicies/observability-networkpolicies.yaml
2a35300 Address observability review findings
504de05 Add observability scrape contracts and harness

$ git show --format=fuller --name-status 504de05 -- gitops/channels/local/observability/networkpolicies/observability-networkpolicies.yaml | sed -n '1,15p'
commit 504de0526e34b431282092f78ed732f7f771af1e
AuthorDate: Sun Apr 26 19:11:17 2026 -0700
    Add observability scrape contracts and harness
A gitops/channels/local/observability/networkpolicies/observability-networkpolicies.yaml
```

INIT-118 did not touch Crossplane or the observability policy in the reviewed surface:

```text
$ git show --format=fuller --name-status 2125d6e -- gitops/channels/local/applications/web gitops/channels/local/security gitops/channels/local/app-clusters/crossplane | sed -n '1,18p'
commit 2125d6e5d76f1a7187ca066eb329e4ad4d1d80fc
AuthorDate: Mon Apr 27 06:49:30 2026 -0700
    feat: SLICE-118.09 gitops ci web workload (INIT-118)
A gitops/channels/local/applications/web/deployment.yaml
A gitops/channels/local/applications/web/networkpolicy.yaml
A gitops/channels/local/applications/web/service.yaml
```

`gitops/channels/local/applications/web/networkpolicy.yaml` is scoped to `namespace: web`, selector `app.kubernetes.io/name: server-manager-web`, and port `8080`.

Adjacent evidence: CNPG webhooks show the same 502 pattern, so the issue likely extends to operator namespaces with all-pods observability ingress policies:

```text
$ docker logs --since=2h k3d-humility-local-server-0 2>&1 | grep -iE 'cnpg-webhook-service|10\.42\.0\.17|Bad Gateway' | tail -5
W0427 20:12:40.266071 76 dispatcher.go:210] Failed calling webhook, failing open mcluster.cnpg.io: failed to call webhook ... proxy error from 127.0.0.1:6443 while dialing 10.42.0.17:9443, code 502: 502 Bad Gateway
```

## Root cause hypothesis

### Candidate A — `allow-observability-scrape` unintentionally isolates Crossplane ingress

Confidence: high.

The live `crossplane-system/allow-observability-scrape` NetworkPolicy selects all pods in `crossplane-system`, has `policyTypes: ["Ingress"]`, and only allows ingress from `observability-system`. Under Kubernetes NetworkPolicy semantics, that single policy makes the Crossplane pod ingress-isolated even though no policy is named `default-deny`.

Supporting evidence:

- Kubernetes docs say any selecting ingress policy isolates ingress.
- K3s docs say K3s includes an embedded kube-router NetworkPolicy controller.
- Live agent logs show the network policy controller running.
- Live iptables rules show Crossplane traffic passing through `allow-observability-scrape` and then being rejected when unmatched.
- Same-namespace same-node pod traffic fails to both 8081 and 9443.
- An allowed `observability-system` pod reaches 8081 and the TLS listener on 9443 after policy state settles.
- Kubelet/node-local readiness reaches 8081, matching the documented node-traffic exception and live node-local accept rule.

This also explains why other pod-to-pod traffic can work: those paths either are not ingress-isolated or have explicit allow policies for their sources.

### Candidate B — The 502 is the k3s tunnel/proxy surfacing a policy reject

Confidence: high.

The API server admission dispatcher reports webhook failure, while the k3s process logs a separate line saying it sent an HTTP/1.1 502 to `127.0.0.1` because dialing `10.42.0.18:9443` returned `connect: connection refused`. That is consistent with K3s' documented agent/server tunnel path and with the destination kube-router `REJECT --reject-with icmp-port-unreachable` rule.

Supporting evidence:

- Crossplane Service and EndpointSlice are correct.
- kube-proxy service DNAT exists.
- The error names the endpoint IP, not a DNS or Service lookup failure.
- The Crossplane listener is active on 9443.
- The destination NetworkPolicy chain explicitly rejects unmatched traffic.

### Candidate C — Crossplane listener binding or startup race

Confidence: low as root cause.

The init container completed webhook setup, the main container listens on all addresses for 8081 and 9443, the pod has no restarts, node-local readiness works, and an allowed namespace reaches the webhook TLS listener. Failures continue long after startup. The investigation did not inspect Crossplane source for the exact handler set, but live evidence weighs against loopback-only binding or startup timing as the primary cause.

### Candidate D — INIT-118 web workload port/CNI conflict

Confidence: low as root cause.

INIT-118 added only the reviewed `web` workload files. The web NetworkPolicy is scoped to namespace `web` and `server-manager-web` pods. It does not select Crossplane, does not alter k3d create flags, and reviewed evidence shows no hostPort collision. Current evidence does not support a port or CNI conflict introduced by INIT-118.

### Candidate E — INIT-107 security baseline as direct cause

Confidence: medium-low as direct cause; medium as enabling context.

INIT-107 introduced the security channel and several NetworkPolicy isolation patterns, but the reviewed INIT-107 files do not create a `crossplane-system` default-deny or `crossplane-system/allow-observability-scrape`. The direct live selector comes from INIT-117 observability work. INIT-107 remains relevant as the earlier security posture that made NetworkPolicy behavior part of the platform contract.

## Affected surface (for downstream proposal phase to scope)

Files implicated by evidence:

- `gitops/channels/local/observability/networkpolicies/observability-networkpolicies.yaml`: all-pods `allow-observability-scrape` for `crossplane-system` and similar operator namespace policies.
- `gitops/channels/local/app-clusters/crossplane/core/rendered/crossplane-1.20.7.yaml`: Crossplane service and port contract.
- `gitops/channels/local/app-clusters/crossplane/core/kustomization.yaml`: inclusion point for the rendered Crossplane core manifest.
- `gitops/channels/local/app-clusters/crossplane/namespace.yaml`: `crossplane-system` namespace metadata and security labels.
- `infra/tests/validate_platform_bootstrap.sh`: existing bootstrap validation harness touched by INIT-107.
- `gitops/channels/local/observability/service-monitors/service-monitors.yaml`: adjacent scrape-intent surface.

Adjacent blast radius:

- `cnpg-system` webhook reachability, confirmed by analogous 502 logs.
- Other operator namespaces with all-pods `allow-observability-scrape` policies and admission/conversion webhooks.
- K3s API server to webhook endpoint traffic.
- Observability scrape traffic from `observability-system`.
- Kubelet/node-local probes, because they do not prove pod-to-pod or API-server webhook reachability.

Tests/checks that would need to encode intended behavior:

- A bootstrap check that the API server can dry-run a Crossplane resource requiring the Crossplane webhook.
- A reachability check to the Crossplane webhook service from a source that represents the API-server admission path or the closest local-cluster proxy.
- A same-namespace operator-webhook reachability check where same-namespace traffic is intended.
- A check that observability scrape reachability remains available from `observability-system`.
- A broader operator-webhook check for CNPG and cert-manager if downstream scope includes the repeated all-pods scrape policy pattern.

No fix design is proposed here; this section only names evidence-bearing surfaces for downstream scoping.

## Open questions

- The exact k3s source function emitting `Sending HTTP/1.1 502 response to 127.0.0.1` was not traced. K3s docs and log shape indicate the control-plane-to-agent tunnel/proxy path, but the function name is unresolved.
- The effective packet source identity for API-server webhook dials under this k3s egress-selector mode was not captured with tcpdump. The iptables reject plus k3s `connect: connection refused` behavior supports the RCA, but packet capture would remove remaining ambiguity.
- The investigation did not enumerate every namespace that combines an all-pods observability ingress policy with a webhook server. CNPG is confirmed adjacent; cert-manager is plausible by pattern but not confirmed by a captured failing event.
- Diagnostic pods emitted PodSecurity warnings because they used the stock `curlimages/curl` security context. They were short-lived and deleted immediately.
