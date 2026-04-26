# INIT-104 Phase 1 Research: S3-Compatible Object Storage

## Scope

- Initiative: INIT-104.
- Phase: 1 research.
- Rule: evidence only; this file does not choose the final proposal design.
- Fixed local backend: MinIO in local k3d.
- Fixed remote backend: Vultr Object Storage.
- Fixed app contract: one S3-compatible SDK path; endpoint and credentials vary by channel.
- Fixed secret boundary: object-storage credentials come from Infisical, not SOPS+age.
- Required output path: `.pipeline/research.md`.
- Research date: 2026-04-26.

## Evidence Index

- E1: `~/.claude3/projects/-home-nes-projects-server-manager/memory/MEMORY.md:1-10` lists the governing project memories and says research work uses the research workflow.
- E2: `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md:11-27` states the same stack runs locally and remotely, with MinIO local and Vultr Object Storage remote under an S3-compatible API.
- E3: `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md:38-43` says per-channel YAML carries provider, endpoint, and credential differences.
- E4: `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md:49-60` defines Phase 5 completion, including local k3d, Flux, Infisical, and MinIO.
- E5: `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md:70-77` names MinIO local object storage and channel YAML extension as corrective initiatives.
- E6: `~/.claude3/projects/-home-nes-projects-server-manager/memory/channel-template-pattern.md:24-39` describes channel identity, parent inheritance, exposure class, and per-channel targets.
- E7: `~/.claude3/projects/-home-nes-projects-server-manager/memory/channel-template-pattern.md:67-74` says all initiatives should use channel id instead of fixed dev/staging/prod roots.
- E8: `DECISIONS.md:176-204` records D8: local-as-first-deployment, k3s everywhere, Flux, Infisical, channel templates, and real local done state.
- E9: `DECISIONS.md:229-237` records that old MinIO claim buses are superseded, but MinIO survives as local S3-compatible storage and Vultr Object Storage is the remote side.
- E10: `product-strategy/tickets/PHASE_5_INDEX.md:26-45` lists INIT-104 scope and dependencies.
- E11: `product-strategy/tickets/PHASE_5_INDEX.md:96-148` records operating rules and completion criteria, including MinIO and backup/restore against local MinIO.
- E12: `../init-103-infisical-runtime-secrets/.pipeline/proposal.md:23-47` defines INIT-103 scope and anti-scope.
- E13: `../init-103-infisical-runtime-secrets/.pipeline/proposal.md:49-95` lists the INIT-103 file surface.
- E14: `../init-103-infisical-runtime-secrets/.pipeline/proposal.md:124-251` specifies the Infisical channel schema shape and local concrete block.
- E15: `../init-103-infisical-runtime-secrets/.pipeline/implementation.md:23-40` states the INIT-103 local runtime-secret done state.
- E16: `../init-103-infisical-runtime-secrets/.pipeline/implementation.md:66-124` is the INIT-104 object-storage handoff.
- E17: `gitops/README.md:23-36` states Infisical is Flux-reconciled and INIT-104 must add object-storage InfisicalSecret resources outside SOPS.
- E18: `infra/README.md:19-36` lists current local prerequisites and pinned INIT-101/102/103 tools.
- E19: `infra/README.md:118-204` documents the current Infisical runtime-secret substrate and SOPS boundary.
- E20: `infra/README.md:331-350` documents local-cluster validation and says object storage is INIT-104 anti-scope so far.
- E21: `infra/channels/local.yaml:1-42` defines the current local k3d channel and Infisical block.
- E22: `infra/channels/dev.yaml:1-28` defines the current Vultr VM remote planning channel and omits GitOps/Infisical.
- E23: `infra/schemas/platform-channel.schema.json:1-84` defines strict channel top-level fields and local `gitops`/`infisical` requirements.
- E24: `infra/schemas/platform-channel.schema.json:355-407` defines the current `infisical` schema block.
- E25: `gitops/channels/local/kustomization.yaml:1-10` lists the current local channel resources and has no object-storage resource.
- E26: `gitops/channels/local/infisical/sample/infisicalsecret.yaml:1-26` shows the proven sample `InfisicalSecret` pattern.
- E27: `infra/scripts/bootstrap-infisical-identity.sh:20-33` shows the current local project, path, sample secret, and UA Secret names.
- E28: `infra/scripts/bootstrap-infisical-identity.sh:129-144` shows channel-resolution-driven Infisical bootstrap fields.
- E29: `infra/scripts/lint-sops-boundary.py:14-43` defines the allowed encrypted files and runtime-secret-shaped patterns.
- E30: `infra/scripts/lint-sops-boundary.py:87-144` enforces the exact SOPS encrypted file set and rejects runtime-secret-shaped keys.
- E31: `infra/scripts/install-cluster-tools.sh:4-15` pins k3d, Flux, Helm, SOPS, age, and Infisical CLI.
- E32: `services/api/pyproject.toml:1-16` lists API dependencies and does not include an S3 SDK.
- E33: `services/discord/pyproject.toml:1-11` lists Discord daemon dependencies and does not include an S3 SDK.
- E34: `pyproject.toml:1-11` lists root dependencies and does not include an S3 SDK.
- E35: `services/api/app/contracts/compliance.py:92-130` defines evidence submissions with `attachment_ref`.
- E36: `services/api/app/services/compliance_extraction.py:79-125` passes `attachment_ref` to OCR extraction.
- E37: `services/api/app/infrastructure/ocr.py:17-36` defines OCR provider behavior and a not-configured stub.
- E38: MinIO container docs: https://docs.min.io/enterprise/aistor-object-store/installation/container/ lines 547-568.
- E39: MinIO Kubernetes docs: https://docs.min.io/enterprise/aistor-object-store/installation/kubernetes/ lines 545-562.
- E40: MinIO Helm chart landing page: https://helm.min.io/ lines 13-17 and 47-78.
- E41: MinIO AIStor Helm chart values reference: https://docs.min.io/enterprise/aistor-object-store/reference/kubernetes/object-store-helm-chart/ lines 594-627 and 636-646.
- E42: MinIO community Helm chart README: https://raw.githubusercontent.com/minio/minio/master/helm/minio/README.md lines 0-13.
- E43: MinIO community Helm chart values: https://raw.githubusercontent.com/minio/minio/master/helm/minio/values.yaml lines 4-18.
- E44: MinIO `mc mb` docs: https://docs.min.io/enterprise/aistor-object-store/reference/cli/mc-mb/ lines 546-565 and 627-654.
- E45: MinIO AdminJob docs: https://docs.min.io/enterprise/aistor-object-store/reference/kubernetes/adminjob/ lines 578-602.
- E46: Vultr Object Storage provisioning docs: https://docs.vultr.com/products/cloud-storage/object-storage/provisioning lines 104-122 and 129-218.
- E47: Vultr Object Storage security guide: https://docs.vultr.com/platform/security-best-practices/vultr-object-storage lines 99-149.
- E48: Vultr S3 compatibility matrix: https://docs.vultr.com/products/cloud-storage/object-storage/s3-compatibility-matrix lines 97-127.
- E49: Vultr Object Storage Terraform resource docs: https://docs.vultr.com/reference/terraform/resources/object_storage lines 180-220.
- E50: Vultr Object Storage Terraform state guide: https://docs.vultr.com/how-to-store-terraform-state-in-vultr-object-storage lines 96-118 and 145-171.
- E51: Vultr Object Storage FAQ: https://docs.vultr.com/products/cloud-storage/object-storage/faq lines 140-157.
- E52: Vultr billing docs: https://docs.vultr.com/support/platform/billing/how-is-object-storage-billed lines 207-219.
- E53: Vultr limits docs: https://docs.vultr.com/products/cloud-storage/object-storage/limits lines 105-129.
- E54: Vultr performance docs: https://docs.vultr.com/products/cloud-storage/object-storage/storage-performance-object-storage lines 106-118 and 216-220.
- E55: Vultr Python guide: https://docs.vultr.com/how-to-use-vultr-object-storage-in-python lines 78-96 and 119-124.
- E56: Boto3 session docs: https://docs.aws.amazon.com/boto3/latest/reference/core/session.html lines 564-608.
- E57: AWS CLI S3 configuration docs: https://docs.aws.amazon.com/cli/latest/topic/s3-config.html lines 56-76.
- E58: Toolchain check run in this worktree on 2026-04-26: `mc` missing; `aws` present at `/home/nes/.local/bin/aws`, version `aws-cli/2.34.6`.
- E59: Toolchain check run in this worktree on 2026-04-26: `kubectl v1.34.1`, `flux v2.8.6`, `k3d v5.8.3`, `sops 3.12.2`, `age v1.3.1`, `infisical 0.43.78`, `helm v3.20.2`, `tofu v1.11.5`, `docker 29.4.0`, and `jq 1.7.1` were present.

## 1. Current Repo State

### 1.1 Governing Phase 5 facts

- Local is a deployment target, not a simulation. [E2, E4, E8]
- The same components run locally and remotely, and only provider/endpoint config differs by channel. [E2, E3]
- Object storage is explicitly MinIO in the local channel and Vultr Object Storage in remote channels. [E2, E5, E9]
- The app-facing commonality is the S3-compatible API. [E2, E9, E10]
- Channel YAML is the expected carrier for provider, endpoint, and credential references. [E3, E6, E7]
- Phase 5 completion requires MinIO serving the S3-compatible object store locally. [E4, E11]
- Phase 5 completion also requires backup and restore against local MinIO later in INIT-112. [E11]
- INIT-104 sits after INIT-103 and before INIT-111/112/113 storage consumers. [E10]
- SOPS+age is bootstrap-only, and Infisical is the runtime secret store. [E8, E15, E19]
- D8 rejects provider-native-only object storage as the app-facing abstraction. [E9]

### 1.2 INIT-103 substrate available

- INIT-103 completed a real Infisical server, Operator, UA Secret, and sample sync path. [E15]
- The local Infisical server endpoint is `http://infisical.infisical-system.svc.cluster.local:8080`. [E16, E21, E26]
- The current local project is `platform-local`, with environment `local`. [E16, E21, E26, E27]
- The sample path `/sample` is already proven by INIT-103. [E16, E26, E27]
- The Operator namespace is `infisical-system`. [E16, E21, E26]
- The Universal Auth Secret is `infisical-operator-auth` in `infisical-system`. [E16, E26, E27]
- The sample consumer namespace is `infisical-sample`. [E16, E26]
- The current `InfisicalSecret` pattern uses `secrets.infisical.com/v1alpha1`. [E26]
- The current pattern reads UA credentials through `credentialsRef.secretName` and `secretNamespace`. [E26]
- The current pattern maps `projectSlug`, `envSlug`, `secretsPath`, and `recursive`. [E26]
- The current pattern writes a managed Kubernetes Secret with `creationPolicy: Owner`. [E26]
- The bootstrap script resolves Infisical values from channel YAML rather than hardcoding every value. [E28]

### 1.3 INIT-104 handoff from INIT-103

- INIT-104 must not create a parallel SOPS path, Helm runtime path, or alternate secret-management system. [E16]
- INIT-104 storage credentials are bound to Infisical project `platform-storage`. [E16]
- The storage path shape is `/object-storage/<channel>/...`. [E16]
- Local MinIO keys are `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`. [E16]
- Remote Vultr keys are `VULTR_OS_ACCESS_KEY` and `VULTR_OS_SECRET_KEY`. [E16]
- INIT-104 authors its own `InfisicalSecret` resources in the object-storage namespace it owns. [E16]
- The expected local consumer namespace is `minio-system`. [E16]
- INIT-104 still has an open choice between reusing the INIT-103 UA credential and creating an INIT-104-owned Machine Identity. [E16]
- MinIO and Vultr Object Storage credentials must not be added to `gitops/bootstrap/`. [E16, E17]
- MinIO and Vultr Object Storage credentials must not be added to any SOPS-encrypted file. [E16, E17, E29, E30]

### 1.4 Current local GitOps and channel files

- `gitops/channels/local/kustomization.yaml` currently includes namespace, generated marker, two bootstrap encrypted files, and Infisical server/operator/sample. [E25]
- The local GitOps kustomization has no object-storage directory today. [E25]
- `gitops/README.md` says INIT-104 must add object-storage `InfisicalSecret` resources in the owning namespace. [E17]
- `infra/README.md` explicitly lists object storage, MinIO, Vultr Object Storage, and S3 backup targets as INIT-104/112 anti-scope so far. [E20]
- The local channel currently has no `object_storage` block. [E21]
- The remote `dev` channel currently has no `object_storage` block. [E22]
- The channel schemas currently define `infisical` but not `object_storage`. [E23, E24]
- The existing schema pattern uses `additionalProperties: false`. [E23, E24]
- The existing local conditional requires `gitops` and `infisical` for `k3d-local`. [E23]
- The resolved-channel pattern already validates inherited Infisical fields. [E20, E28]

### 1.5 Current app/storage usage

- Root Python dependencies are `discord.py`, `python-dotenv`, `aiohttp`, and `PyYAML`; no S3 SDK appears there. [E34]
- API dependencies include FastAPI, psycopg, Pydantic, SQLAlchemy, uvicorn, and dotenv; no S3 SDK appears there. [E32]
- Discord daemon dependencies include discord.py, Pydantic, pydantic-settings, and dotenv; no S3 SDK appears there. [E33]
- Repo search found no `boto3`, `botocore`, `aws-sdk`, `@aws-sdk`, `minio`, or `S3Client` import in application code during this research run. [E32, E33, E34]
- Existing compliance evidence contracts store an `attachment_ref` string. [E35]
- Compliance extraction passes `attachment_ref` directly to an OCR provider. [E36]
- The OCR provider is still an abstraction and the shipped provider is not configured. [E37]
- Tests currently use `s3://bucket/evidence.png` as a literal attachment reference, not as SDK-backed object access. [E35, E36]
- There is therefore no current app S3 client wrapper to preserve or extend. [E32, E33, E34, E35, E36, E37]

## 2. MinIO Self-Hosted Architecture

### 2.1 Packaging shapes in evidence

- MinIO documents container deployment for local development and evaluation. [E38]
- MinIO documents Kubernetes deployment through a first-party Operator model. [E39]
- The current MinIO Helm landing page says AIStor runs in Kubernetes and requires a Kubernetes environment, `kubectl`, and Helm. [E40]
- The same Helm page shows the current object-store Operator install path. [E40]
- The same Helm page shows `aistor-objectstore` chart installation as a separate object store step. [E40]
- The current AIStor Operator page states that the object-store Operator requires a valid license value. [E40]
- The MinIO community chart README says the community chart is community built and not guaranteed for support by MinIO. [E42]
- The community chart README says MinIO strongly recommends the official Operator for production deployments. [E42]
- The community chart still documents a minimal toy setup using `mode=standalone`, `replicas=1`, `persistence.enabled=false`, and `resources.requests.memory=512Mi`. [E42]
- The community chart supports an existing Kubernetes Secret for root credentials. [E42]
- The community values expose `mode` with supported value `standalone`. [E43]
- The community values expose API port `9000` and console port `9001`. [E43]
- The community values default to persistence enabled. [E43]
- The community values show default persistence size `500Gi`. [E43]
- The community values show `service.type: ClusterIP` and service port `9000`. [E43]
- The community values show `consoleService.type: ClusterIP` and port `9001`. [E43]
- The community values show a default memory request of `16Gi`, while the README toy setup shows `512Mi`. [E42, E43]
- The community values include `makeBucketJob` and a `buckets` list for post-install bucket creation. [E43]
- The official AIStor chart values reference has an existing-secret mechanism where `config.env` can export `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`. [E41]
- The official AIStor chart values reference shows image repository and timestamp-style release tag configuration. [E41]
- The official AIStor container docs recommend file-based environment variables for production container orchestration credentials. [E38]

### 2.2 Component subset for local k3d

- The local done state only needs a real S3-compatible endpoint, not HA object-storage durability. [E2, E4, E11]
- A single-node MinIO process is documented as a local development/evaluation container shape. [E38]
- A Kubernetes Operator/Tenant path exists, but it brings first-party Operator resources and license-oriented AIStor packaging. [E39, E40]
- The community chart can render a standalone toy setup, but its README says it is community maintained and not guaranteed for support. [E42]
- The current repo precedent from INIT-103 is committed raw manifests rendered from Helm, with no Helm controller. [E13, E17, E19]
- The current Flux substrate includes source-controller and kustomize-controller only. [E17, E20]
- The current repo has no HelmRelease/Helm controller runtime path for INIT-104 to reuse. [E17, E20]
- The evidence set therefore separates three possible packaging inputs for proposal: raw authored manifests, rendered community chart YAML, and Operator/Tenant manifests. [E17, E39, E40, E42]
- The Operator path has more moving parts than a raw single-server Pod/Service/PVC because it adds Operator-managed custom resources. [E39, E40, E45]
- The raw manifest path matches the current Flux/Kustomize substrate shape most directly because current local channel resources are plain Kustomize resources. [E17, E25]

### 2.3 Image and resource evidence

- MinIO image tags in chart examples use timestamped `RELEASE.<date>` style tags. [E41, E43]
- The current project pins tool and chart versions in scripts and rendered YAML rather than floating them. [E13, E31]
- The proposal phase needs to choose a concrete MinIO server image tag and a concrete `mc` image tag. [E41, E43]
- The community chart values reference `quay.io/minio/minio` as the MinIO repository. [E43]
- The community chart values reference `quay.io/minio/mc` as the `mc` image used for bucket jobs. [E43]
- The local k3d cluster shape is one server and one agent. [E21]
- The community chart default memory request is large for local k3d at `16Gi`; its toy setup documents `512Mi`. [E42, E43]
- The community chart default PVC size is `500Gi`, which is much larger than a sample-bucket proof needs. [E43]
- The proposal phase needs a local PVC size small enough for developer machines while still proving persistence. [E21, E42, E43]
- The available evidence supports a local PVC sizing discussion, but does not provide a project-specific required number. [E21, E42, E43]

### 2.4 Ports, console, and credentials

- MinIO API port evidence is `9000`. [E43]
- MinIO console port evidence is `9001`. [E43]
- The requested internal endpoint `http://minio.minio-system.svc.cluster.local:9000` matches ClusterIP API access on port `9000`. [E43]
- The console can remain cluster-internal through ClusterIP just like the API Service. [E43]
- The official chart values reference `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` as exported environment variables in `config.env`. [E41]
- INIT-103 binds those same local key names for INIT-104. [E16]
- The community chart existing-Secret path expects `rootUser` and `rootPassword` keys, which differs from the INIT-103 handoff key names. [E16, E42]
- A raw manifest can consume an Infisical-synced Secret with environment variable keys named exactly as INIT-103 specified. [E16, E41]
- The proposal phase needs to decide Kubernetes Secret name and key casing for local MinIO consumers. [E16]

### 2.5 Bucket creation evidence

- `mc mb` creates a bucket on a MinIO deployment. [E44]
- `mc mb` can also create buckets on S3-compatible services. [E44]
- `mc mb` supports `--ignore-existing`, which is relevant to idempotent jobs. [E44]
- `mc mb` supports a region flag, defaulting to `us-east-1` if unspecified. [E44]
- The community chart includes a `buckets` list and `makeBucketJob` for post-install bucket creation. [E43]
- MinIO AdminJob supports a structured `make-bucket` operation when using the Operator path. [E45]
- AdminJob executes AIStor Client commands through Kubernetes Jobs. [E45]
- A non-Operator raw manifest path can still use an ordinary Kubernetes Job running `mc` after MinIO readiness. [E43, E44]
- The evidence does not show S3 PUT auto-creating buckets; bucket creation is explicit in `mc`, Boto3, s3cmd, or Vultr Console/API flows. [E44, E47, E55]

## 3. Vultr Object Storage

### 3.1 Architecture and provisioning

- Vultr Object Storage is S3-compatible storage for objects. [E46]
- Vultr provisioning supports Console, API, CLI, and Terraform paths. [E46]
- Console provisioning starts in Products > Cloud Storage > Object Storage. [E46]
- API provisioning uses clusters, tiers, and a `POST /v2/object-storage` request. [E46]
- CLI provisioning uses `vultr-cli object-storage create --cluster-id ... --label ...`. [E46]
- Terraform provisioning uses `vultr_object_storage` with `cluster_id`, `tier_id`, and `label`. [E46, E49]
- The Terraform resource exports `region`, `s3_access_key`, `s3_hostname`, and `s3_secret_key`. [E49]
- Vultr cluster lookup by region exists through `vultr_object_storage_cluster`. [E46]
- Existing `infra/bootstrap/state-backend` already refers to Vultr object storage for tfstate bootstrap, but INIT-104 is the app/runtime object-storage layer. [E20, E50]

### 3.2 Regions and endpoints

- Vultr documents endpoints following `<region>.vultrobjects.com`. [E47]
- Vultr gives `ewr1.vultrobjects.com` as a New Jersey endpoint example. [E47, E50, E51]
- Vultr FAQ lists Amsterdam as `ams1.vultrobjects.com`. [E51]
- Vultr FAQ lists Bangalore as `blr1.vultrobjects.com`. [E51]
- Vultr FAQ lists New Jersey as `ewr1.vultrobjects.com`. [E51]
- Vultr FAQ lists Silicon Valley as `sjc1.vultrobjects.com`. [E51]
- Vultr FAQ lists Singapore as `sgp1.vultrobjects.com`. [E51]
- Vultr FAQ lists New Delhi as `del1.vultrobjects.com`. [E51]
- The current dev channel uses Vultr region `ewr`. [E22]
- The expected remote endpoint `https://ewr1.vultrobjects.com` aligns with the current dev channel region and Vultr endpoint examples. [E22, E47, E50, E51]

### 3.3 Credentials and client configuration

- Vultr Object Storage authenticates with S3-style access and secret keys scoped to the subscription. [E47]
- Vultr tells operators to store keys in a secrets manager. [E47]
- Vultr Terraform state docs use `AWS_ACCESS_KEY` and `AWS_SECRET_ACCESS_KEY` environment variables for S3 compatibility. [E50]
- Vultr Terraform resource docs expose `s3_access_key` and `s3_secret_key`. [E49]
- INIT-103 handoff names remote Infisical keys as `VULTR_OS_ACCESS_KEY` and `VULTR_OS_SECRET_KEY`. [E16]
- Vultr client guidance says use the correct regional endpoint, S3 credentials, preferred addressing style, HTTPS, and Signature V4. [E47]
- Vultr s3cmd example sets `signature_v4 = True`. [E47]
- Vultr state guide says `region = us-east-1` even though Vultr ignores the value for that Terraform backend case. [E50]
- Boto3 supports `region_name`, `endpoint_url`, `aws_access_key_id`, and `aws_secret_access_key` when creating a service client. [E56]
- AWS CLI S3 commands support `--endpoint-url` for custom endpoints. [E57]
- AWS CLI S3 config includes addressing style values `path`, `virtual`, and `auto`. [E57]
- Vultr recommends virtual-host style for better CDN interoperability, while noting SDKs may default to path-style. [E47]
- A local MinIO service endpoint inside the cluster will normally be path-style friendly because the bucket is not encoded into DNS. [E43, E47, E57]
- The proposal phase needs to record whether app SDK config forces path-style for local, allows virtual-host for remote, or uses a library default verified against both. [E47, E56, E57]

### 3.4 Bucket creation, compatibility, limits, and pricing

- Vultr documents Console bucket creation after provisioning a subscription. [E47, E50]
- Vultr Python docs show Boto3 `create_bucket(Bucket='example-bucket')`. [E55]
- Vultr S3 compatibility matrix marks `Create Bucket`, `Put Object`, `Get Object`, `Delete Object`, and `List Buckets` as supported. [E48]
- Vultr S3 compatibility matrix marks bucket lifecycle and object versioning as supported. [E48]
- Vultr S3 compatibility matrix marks bucket notification and bucket replication as unsupported. [E48]
- Vultr subscription limits include a default 100-bucket limit. [E53]
- Vultr bucket names must be 3 to 63 characters, or 3 to 53 characters if archival storage may be enabled at creation time. [E53]
- Vultr docs list 400 operations per second in the limits page. [E53]
- Vultr performance docs list tier-specific limits from Standard through Accelerated. [E54]
- Vultr billing docs say all non-archive tiers include 1000 GB storage, 1000 GB outbound transfer, and unlimited inbound transfer. [E52]
- Vultr billing docs list Standard at $18/month, Premium at $36/month, Performance at $50/month, and Accelerated at $100/month as of the cited page. [E52]
- Additional outbound transfer beyond included transfer is billed at $0.01/GB on the cited billing page. [E52]

## 4. Same S3 SDK Path

### 4.1 SDK surface evidence

- The project requirement is one app SDK path with endpoint and credentials differing per channel. [E2, E3, E9, E10]
- Boto3 can create an S3 client with region, endpoint URL, access key, and secret key. [E56]
- AWS CLI can test S3 operations against a custom endpoint using `--endpoint-url`. [E57]
- Vultr's Python guide uses Boto3 for bucket and object operations against Vultr Object Storage. [E55]
- Vultr's S3 compatibility matrix supports the operations needed for PUT/GET round-trip. [E48]
- MinIO exposes an S3-compatible API and `mc` can create buckets on MinIO and S3-compatible services. [E42, E44]
- The app currently has no S3 SDK dependency, so adding the first client wrapper will not replace an existing implementation. [E32, E33, E34]

### 4.2 Local channel values under research

- Local provider is MinIO. [E2, E4, E5, E9]
- Local API endpoint target is `http://minio.minio-system.svc.cluster.local:9000`. [E16, E43]
- Local credentials are sourced from Infisical path `/object-storage/local/`. [E16]
- Local credential keys are `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`. [E16]
- Local Kubernetes consumer namespace is expected to be `minio-system`. [E16]
- Local bucket proof target is a sample bucket such as `humility-local-sample`. [E4, E11, E44]
- Local region can be carried by config even if MinIO does not require AWS region semantics for simple operations. [E44, E56]

### 4.3 Remote channel values under research

- Remote provider is Vultr Object Storage. [E2, E9, E10]
- Remote dev channel currently declares Vultr region `ewr`. [E22]
- Remote endpoint example is `https://ewr1.vultrobjects.com`. [E47, E50, E51]
- Remote credentials are sourced from Infisical path `/object-storage/<channel>/`. [E16]
- Remote credential keys are `VULTR_OS_ACCESS_KEY` and `VULTR_OS_SECRET_KEY`. [E16]
- Vultr client guidance requires HTTPS and Signature V4. [E47]
- Vultr Object Storage supports the same create, put, get, list, and delete operations needed by the local proof contract. [E48]

### 4.4 App-code abstraction implications

- The common minimum config shape is endpoint, access key, secret key, region, and bucket or bucket prefix. [E16, E47, E56, E57]
- The app code should not branch on MinIO versus Vultr for object PUT/GET behavior. [E2, E3, E9]
- The config layer may branch on channel target to resolve endpoint and secret references. [E3, E6, E7]
- The current compliance evidence code already treats object identity as a string reference. [E35, E36]
- The future storage wrapper can convert uploads into `attachment_ref` values without changing OCR provider call shape immediately. [E35, E36, E37]
- The proposal phase needs to decide whether the first SDK proof is Python-only, CLI-only, or both. [E32, E55, E56, E57]

## 5. Infisical Integration

### 5.1 Bound storage credential project

- INIT-103 handoff binds object-storage credentials to Infisical project `platform-storage`. [E16]
- The current local Infisical sample project is `platform-local`; storage uses a different project. [E16, E26, E27]
- The handoff path shape is `/object-storage/<channel>/...`. [E16]
- The environment slug is per channel, such as `local`. [E16, E21, E26]
- Existing InfisicalSecret sample proves project/environment/path sync mechanics. [E26]
- Existing bootstrap code shows channel-driven resolution for project, environment, path, UA Secret name, and namespace. [E28]
- The proposal phase needs to decide how `platform-storage` is bootstrapped in local Infisical. [E16, E27, E28]
- The proposal phase needs to decide whether to create a dedicated INIT-104 Machine Identity. [E16]

### 5.2 Expected local sync shape

- The object-storage `InfisicalSecret` should live under `gitops/channels/local/object-storage/` by INIT-104 scope. [E16, E17, E25]
- The target namespace for local MinIO credentials is expected to be `minio-system`. [E16]
- The source project is `platform-storage`. [E16]
- The source environment is `local` for the local channel. [E16, E21]
- The source path is `/object-storage/local/`. [E16]
- The local keys are `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`. [E16]
- The target Kubernetes Secret name is not yet fixed in the handoff. [E16]
- The recursive-vs-split `InfisicalSecret` choice is open in the handoff. [E16]
- The current `InfisicalSecret` sample includes `includeAllSecrets: true`, which is a reusable pattern only if the storage path contains exactly intended keys. [E26]

### 5.3 Expected remote sync shape

- Remote credentials remain in Infisical and not in SOPS. [E16, E17, E29, E30]
- Remote Vultr keys are `VULTR_OS_ACCESS_KEY` and `VULTR_OS_SECRET_KEY`. [E16]
- Remote endpoint and region are channel config, not secret values by default. [E3, E6, E7, E47]
- Remote channel GitOps/Infisical install is currently omitted in `dev`, so remote apply remains outside INIT-104 local proof unless later remote Flux work exists. [E22]
- The same `InfisicalSecret` CRD pattern can sync remote credentials once remote channel GitOps and Infisical are in scope. [E16, E26]

### 5.4 SOPS boundary

- SOPS encrypted files are currently limited to the Flux sentinel and Infisical server bootstrap files. [E17, E19, E29, E30]
- The SOPS linter rejects runtime-secret-shaped key names, including password and secret access key patterns. [E29, E30]
- MinIO root password fits the linter's runtime-secret-shaped rejection pattern. [E16, E29]
- Vultr secret key fits the linter's runtime-secret-shaped rejection pattern. [E16, E29]
- The research evidence supports treating all object-storage credentials as runtime-only Infisical data. [E16, E17, E19, E29, E30]

## 6. Channel Schema Additions (Sketch)

### 6.1 Existing schema pattern

- Channel schema version is currently `1`. [E23]
- Top-level schema fields are strict with `additionalProperties: false`. [E23]
- Existing optional blocks include `cluster`, `state`, `gitops`, and `infisical`. [E23]
- Local `k3d-local` currently requires `gitops` and `infisical`. [E23]
- The existing `infisical` definition is strict and requires endpoint, project, environment, path, auth, UA Secret metadata, Operator namespace, and resync interval. [E24]
- The current `state` block already has bucket, key, region, and optional endpoint for Terraform state. [E23]
- Any `object_storage` addition must be additive to schema version 1 or trigger a schema version decision. [E23, E24]

### 6.2 Candidate `object_storage` fields for proposal input

- Candidate field: `provider`, enum `minio` or `vultr-os`, reflecting fixed local and remote backends. [E2, E9, E10]
- Candidate field: `endpoint`, URI or hostname depending on whether local includes `http://`. [E43, E47, E50, E56]
- Candidate field: `region`, string, needed by SDK clients even if some providers ignore it. [E50, E56]
- Candidate field: `bucket_prefix`, string, matching channel target prefix concepts in channel memory. [E6]
- Candidate field: `infisical_path`, path string such as `/object-storage/local/`. [E16]
- Candidate field: `credentials_secret_name`, because INIT-103 handoff leaves target Secret names open. [E16]
- Candidate field: `credentials_secret_namespace`, because local MinIO expected namespace is `minio-system` but apps may consume elsewhere later. [E16]
- Candidate local conditional: `cluster.target == k3d-local` implies provider `minio`. [E2, E21]
- Candidate remote conditional: `cluster.target == vultr-vms` implies provider `vultr-os`. [E2, E22]
- Candidate validation: local endpoint should be cluster-internal service URL on port `9000`. [E16, E43]
- Candidate validation: remote endpoint should follow Vultr endpoint pattern. [E47, E51]
- Candidate validation: Infisical path should include the channel id. [E16, E21, E22]

### 6.3 Schema open points

- Open: whether `object_storage` is required for every channel after INIT-104 or only for `k3d-local` first. [E10, E21, E22]
- Open: whether remote `dev` receives an `object_storage` block before remote GitOps exists. [E22]
- Open: whether bucket prefix is global per channel or per application subsystem. [E6, E35]
- Open: whether app namespaces receive credentials directly or via a separate app-facing Secret after MinIO root credentials are separated. [E16]
- Open: whether local MinIO root credentials are also the app test credentials or whether a sample access key is created after boot. [E16, E43, E44]

## 7. Local-First MinIO Done-State

### 7.1 Required proof state

- Local done state must deploy a real component into the local channel. [E8, E11]
- Local object storage done state must include MinIO serving S3-compatible storage. [E4, E11]
- The MinIO server Pod must be Ready in local k3d. [E4, E11, E20]
- The local channel must be reconciled by Flux from `gitops/channels/local`. [E17, E20, E25]
- The object-storage subtree should live under `gitops/channels/local/object-storage/`. [E16, E17, E25]
- The MinIO API should be reachable through a ClusterIP Service at port `9000`. [E16, E43]
- Console exposure is optional for local proof; evidence only requires API round-trip. [E4, E11, E43]
- The credentials must arrive through Infisical-synced Kubernetes Secret, not hardcoded manifests. [E16, E17, E19, E29, E30]

### 7.2 Bucket and object proof

- A sample bucket such as `humility-local-sample` must exist for local proof. [E4, E11, E44]
- Bucket creation is explicit through `mc mb`, Boto3 `create_bucket`, s3cmd, the chart job, or Operator AdminJob. [E43, E44, E45, E55]
- The sample object proof requires a PUT and GET. [E48, E55, E57]
- GET should verify exact content, not only HTTP success. [E48, E55]
- `mc mb --ignore-existing` provides idempotent bucket creation input if `mc` is used. [E44]
- Boto3 client parameters support the same endpoint/credential/region inputs needed by local and remote proof. [E56]
- AWS CLI `--endpoint-url` can test the local MinIO endpoint once credentials are present. [E57]
- The proof should demonstrate the app-facing contract rather than only Kubernetes readiness. [E2, E4, E11, E56, E57]

### 7.3 Harness implications

- Current cluster harness already verifies k3d, Flux, Infisical server, Operator, UA, and sample secret readiness. [E20]
- INIT-104 harness can extend the same local-cluster path instead of inventing a separate cluster bring-up. [E20]
- Current cluster harness requires Docker, k3d, kubectl, flux, helm, sops, age, age-keygen, and infisical. [E20]
- INIT-104 adds `mc` and/or AWS CLI as object-storage proof tools. [E44, E57, E58]
- The current local channel already has one server and one agent, which constrains resource sizing. [E21]
- The harness should distinguish missing `mc` from missing `aws`, because current workstation has AWS CLI but not `mc`. [E58]

## 8. Toolchain Check

### 8.1 Existing INIT-101/102/103 tools

- `infra/scripts/install-cluster-tools.sh` pins k3d `v5.8.3`. [E31]
- The local machine has k3d `v5.8.3`. [E59]
- `infra/scripts/install-cluster-tools.sh` pins Flux `v2.8.6`. [E31]
- The local machine has Flux `v2.8.6`. [E59]
- `infra/scripts/install-cluster-tools.sh` pins Helm `v3.20.2`. [E31]
- The local machine has Helm `v3.20.2`. [E59]
- `infra/scripts/install-cluster-tools.sh` pins SOPS `v3.12.2`. [E31]
- The local machine has SOPS `3.12.2`. [E59]
- `infra/scripts/install-cluster-tools.sh` pins age `v1.3.1`. [E31]
- The local machine has age and age-keygen `v1.3.1`. [E59]
- `infra/scripts/install-cluster-tools.sh` pins Infisical CLI `v0.43.78`. [E31]
- The local machine has Infisical CLI `0.43.78`. [E59]
- The local machine has kubectl client `v1.34.1`. [E59]
- The local machine has OpenTofu `v1.11.5`. [E59]
- The local machine has Docker `29.4.0`. [E59]
- The local machine has jq `1.7.1`. [E59]

### 8.2 Object-storage tools

- `mc` was not found on PATH during this research run. [E58]
- AWS CLI was found at `/home/nes/.local/bin/aws`. [E58]
- AWS CLI version was `aws-cli/2.34.6`. [E58]
- MinIO docs identify `mc` as the native client used for bucket creation. [E44]
- Vultr docs list S3-compatible tools and SDKs as valid Object Storage clients. [E51]
- AWS CLI docs support custom endpoint testing through `--endpoint-url`. [E57]
- `mc` install evidence exists through MinIO download metadata, but the local installer does not currently install it. [E31, E44, E58]
- The proposal phase should decide whether `mc` becomes a pinned tool in `install-cluster-tools.sh`. [E31, E44, E58]
- The proposal phase should decide whether AWS CLI is formally pinned or treated as optional host tooling. [E57, E58]

## 9. Known Risks and Open Questions

### 9.1 BLOCKS_PROPOSAL

- BLOCKS_PROPOSAL: MinIO raw manifests vs rendered community chart vs Operator must be selected before implementation scope is stable. [E39, E40, E42, E43, E45]
- BLOCKS_PROPOSAL: If Operator is selected, the proposal must handle AIStor license and CRD/operator blast radius. [E39, E40, E45]
- BLOCKS_PROPOSAL: If raw manifests are selected, the proposal must specify how bucket creation and readiness waits are represented declaratively. [E25, E43, E44]
- BLOCKS_PROPOSAL: The target Kubernetes Secret name and key casing for MinIO credentials are open. [E16]
- BLOCKS_PROPOSAL: The project `platform-storage` bootstrapping path is open. [E16, E27, E28]
- BLOCKS_PROPOSAL: Dedicated INIT-104 Machine Identity vs reused INIT-103 UA credential is open. [E16]
- BLOCKS_PROPOSAL: The channel schema requirement for remote channels is open because current `dev` lacks GitOps/Infisical. [E22, E23]

### 9.2 BLOCKS_IMPLEMENTATION

- BLOCKS_IMPLEMENTATION: `mc` is not installed locally. [E58]
- BLOCKS_IMPLEMENTATION: The installer does not currently pin or install `mc`. [E31, E58]
- BLOCKS_IMPLEMENTATION: No MinIO manifests exist under the local channel today. [E20, E25]
- BLOCKS_IMPLEMENTATION: No object-storage channel schema fields exist today. [E23, E24]
- BLOCKS_IMPLEMENTATION: No S3 SDK dependency exists in the app services today. [E32, E33, E34]
- BLOCKS_IMPLEMENTATION: MinIO credential values are not present in the repo and must be supplied through Infisical. [E16, E17, E19]
- BLOCKS_IMPLEMENTATION: Remote Vultr bucket/subscription credentials cannot be hardcoded or placed in SOPS. [E16, E17, E29, E30]
- BLOCKS_IMPLEMENTATION: Local proof requires a running local cluster with Infisical already reconciled. [E15, E16, E20]

### 9.3 INFORMATIONAL

- INFORMATIONAL: Vultr bucket names are limited to 3-63 characters, or 3-53 for archival-enabled buckets. [E53]
- INFORMATIONAL: Vultr subscriptions default to 100 buckets. [E53]
- INFORMATIONAL: Vultr compatibility does not include bucket replication or bucket notification. [E48]
- INFORMATIONAL: Vultr Standard/Premium use HDD with flash/SSD metadata and cache characteristics, while Performance/Accelerated use NVMe. [E54]
- INFORMATIONAL: Vultr performance docs recommend client-side parallelism and honoring 429s. [E54]
- INFORMATIONAL: Vultr files are private by default and require credentials unless permissions are changed. [E50]
- INFORMATIONAL: Vultr Object Storage does not provide Terraform backend locking. [E50]
- INFORMATIONAL: MinIO community chart default memory and PVC values are larger than a local proof needs. [E42, E43]
- INFORMATIONAL: MinIO Console can remain internal unless a later route/ingress initiative exposes it. [E43]
- INFORMATIONAL: Current compliance code uses `attachment_ref` strings, so storage integration can begin at object-reference production before OCR fetch logic exists. [E35, E36, E37]

### 9.4 Specific open questions

- Open: Is the local bucket job a raw Kubernetes Job using `mc`, a rendered chart post-job, or an Operator AdminJob? [E43, E44, E45]
- Open: Should bucket creation use root credentials or a separate access key created after startup? [E16, E41, E43]
- Open: Does the sample round-trip script use Boto3, AWS CLI, `mc`, or more than one client? [E44, E55, E56, E57]
- Open: Should local region be `us-east-1`, `local`, or a channel-defined Vultr-like region for parity? [E44, E50, E56]
- Open: Should SDK config force path-style for both local and remote, or vary addressing style by endpoint? [E47, E57]
- Open: Does remote bucket creation belong to Vultr API/Terraform, S3-compatible client, or deployment runbook? [E46, E47, E49, E55]
- Open: Vultr does not auto-create buckets on first PUT in the cited evidence; bucket creation is explicit. [E47, E48, E55]
- Open: Should `/object-storage/<channel>/...` be recursive in one CR or split by provider/key set? [E16, E26]
- Open: Should app workloads consume MinIO root credentials for local proof or a least-privilege app credential? [E16, E41, E43]
- Open: What rotation requirements belong to INIT-104 versus INIT-115 access policy/service identity? [E16]

## 10. Suggested Slice Decomposition (Sketch)

### 10.1 Slice list

- SLICE-104.01: Toolchain installer for `mc`, with AWS CLI documented as present or optional. [E31, E44, E57, E58]
- SLICE-104.02: Local MinIO manifests under `gitops/channels/local/object-storage/`. [E16, E17, E25]
- SLICE-104.03: Storage `InfisicalSecret` CR syncing `platform-storage` path `/object-storage/local/` into `minio-system`. [E16, E26]
- SLICE-104.04: Channel schema addition for `object_storage`. [E3, E6, E7, E23, E24]
- SLICE-104.05: Bucket creation mechanism for `humility-local-sample`. [E43, E44, E45]
- SLICE-104.06: Sample S3 round-trip script using endpoint, region, access key, secret key, bucket, and object key. [E48, E55, E56, E57]
- SLICE-104.07: Harness extension: Pod Ready, Secret synced, bucket exists, PUT/GET content verified. [E20, E44, E48, E57]
- SLICE-104.08: Vultr Object Storage contract documentation for remote endpoint, credentials, bucket creation, pricing, and limits. [E46, E47, E48, E51, E52, E53]
- SLICE-104.09: Documentation and INIT-105/111/112/113 handoff. [E10, E11, E35, E36]

### 10.2 Proposal-phase priority inputs

- Priority 1: choose MinIO install shape under D8 and INIT-102 constraints. [E8, E17, E20, E39, E40, E42, E43, E45]
- Priority 2: lock the Infisical `platform-storage` bootstrap and Kubernetes Secret contract. [E16, E26, E27, E28]
- Priority 3: lock the local proof contract: bucket creation, SDK/CLI client, and exact PUT/GET verification. [E44, E48, E55, E56, E57]

### 10.3 Evidence-based install-shape observation for proposal

- The lowest-moving-parts local shape in the evidence is raw Kustomize-managed Kubernetes resources: Namespace, Secret synced by InfisicalSecret, PVC, MinIO workload, Service, and a post-readiness bucket Job. [E16, E17, E25, E26, E41, E43, E44]
- The raw shape matches the existing Flux substrate because current local channel reconciliation is plain Kustomize resources, not HelmRelease. [E17, E20, E25]
- The Operator shape is official for production Kubernetes, but brings Operator/CRD/AdminJob machinery and current AIStor chart licensing evidence. [E39, E40, E45]
- The community chart shape has built-in post-install bucket jobs, but the README says it is community supported and not guaranteed by MinIO. [E42, E43]
- Bucket creation evidence favors an idempotent post-readiness Job using `mc mb --ignore-existing` if raw manifests are selected. [E43, E44]
- This observation is proposal input, not a final design decision. [E8]

## Appendix A: Toolchain Availability Summary

- `mc`: missing from PATH on 2026-04-26. [E58]
- `aws`: present at `/home/nes/.local/bin/aws`, version `aws-cli/2.34.6`. [E58]
- `kubectl`: present, client `v1.34.1`. [E59]
- `k3d`: present, `v5.8.3`. [E59]
- `flux`: present, `v2.8.6`. [E59]
- `helm`: present, `v3.20.2`. [E59]
- `sops`: present, `3.12.2`. [E59]
- `age`: present, `v1.3.1`. [E59]
- `age-keygen`: present, `v1.3.1`. [E59]
- `infisical`: present, `0.43.78`. [E59]
- `tofu`: present, `v1.11.5`. [E59]
- `docker`: present, `29.4.0`. [E59]
- `jq`: present, `1.7.1`. [E59]

## Appendix B: Non-Solution Boundary

- This research does not implement MinIO. [E20, E25]
- This research does not create Infisical credentials. [E16, E17, E19]
- This research does not create Vultr Object Storage subscriptions or buckets. [E46, E47]
- This research does not add S3 SDK dependencies. [E32, E33, E34]
- This research does not change channel schema files. [E23, E24]
- This research does not commit changes. [E8]
