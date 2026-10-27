# ENTER t3.medium resize readiness — 24 October 2026

## Decision

**NOT SAFE TO RESIZE YET.** The 4 GiB capacity and isolated recovery workload
passed, but production rollback protection and access are not ready: the newest
database object is stale, there is no EBS snapshot, the instance has no Elastic
IP, and the host is not reachable through SSM or the currently permitted SSH
sources.

No production instance, DNS, billing, candidate registration, resume upload,
AI setting, or candidate record was changed during this review.

## 4 GiB capacity and recovery test

The isolated rehearsal used reviewed production application images, real ClamAV,
fictional candidates, local S3/SQS/email emulators, and disabled AI. All six
production-like containers plus the 768 MiB scratch PostgreSQL restore shared a
3 GiB cgroup with swap disabled, reserving about 1 GiB for a 4 GiB host's OS and
Docker overhead.

- Aggregate memory limit: 3,221,225,472 bytes (3 GiB)
- Peak: 2,193,375,232 bytes (2.043 GiB)
- Remaining constrained-container headroom: 1,027,850,240 bytes (0.957 GiB)
- Swap used: 0
- Aggregate OOM / OOM-kill / limit-hit events: 0 / 0 / 0
- FreshClam updated daily signatures from 28150 to 28162, tested the database,
  notified clamd, and clamd completed the reload with 3,628,191 signatures.
- A worker job was confirmed in `processing` state while clamd reloaded, a
  consistent custom-format dump ran, and the 768 MiB/no-swap scratch database
  restored the archive. `pg_amcheck` passed; 39 migrations were readable and
  there were zero invalid indexes.
- A scan attempted during the non-concurrent engine reload failed closed and was
  retried successfully. No resume was marked clean before a successful scan.
- Synthetic resume batches at concurrency 1, 5, and 10 drained successfully.
  The concurrency-10 batch completed in about 31 seconds in the emulated local
  amd64 environment. This is capacity evidence, not a Sydney latency promise.
- Test cleanup left zero fictional candidate profiles and zero processing jobs.

The production backup preflight now requires 1.25 GiB available before both the
dump and isolated-restore phases instead of the incompatible 3 GiB requirement.
The restore remains capped at 768 MiB, no swap, 0.5 CPU, 384 MiB tmpfs, no
network and no live-data mounts. Backup orchestration tests: 69 passed, 8 skipped;
Ruff passed.

## Current production protection and access

- Instance: `i-08f84202dbb6b4cce`, running `m7i-flex.large` in Sydney.
- Root volume: encrypted 30 GiB gp3 `vol-09659dd92c912378d`.
- EBS snapshots for that volume: none.
- Elastic IP: none. Current automatic public IPv4: `3.26.28.4`.
- `enter.careers` resolves to that address with an approximately 30-minute TTL.
- SSM inventory: no connected managed instance.
- The instance has the `ENTER-Staging-EC2-Role` and key pair
  `enter-staging-key`, but SSH is limited to two fixed `/32` sources that do not
  provide access from the current operator host. No EC2 Instance Connect Endpoint
  exists.
- Newest database object: `postgres/hourly/2026/10/23/123410-...dump`, written
  23 October 2026 12:34:12 UTC. No 24 October hourly or daily object was present.
- That object is 188,197 bytes, SSE-S3 (`AES256`) encrypted, and has a SHA-256
  checksum. Bucket Block Public Access is fully enabled. Bucket versioning is not
  enabled.
- Object existence and checksum do not prove the post-upload restore completed;
  the verified marker is stored on the inaccessible host.

## Remaining gates

1. Restore controlled host access by reconnecting SSM or authorizing the current
   operator `/32` for SSH; do not open SSH broadly.
2. Diagnose the stopped/stale backup schedule, run a fresh hourly and daily backup,
   and confirm both private verified-success markers after isolated restores.
3. Perform one independently selected historical restore drill.
4. Create and wait for a pre-resize encrypted EBS snapshot. Snapshot creation has
   ongoing storage cost and requires explicit approval.
5. Allocate an Elastic IP, perform a controlled Namecheap A-record cutover, wait
   through the TTL, and confirm public HTTPS before the resize window. This also
   requires explicit approval because it changes the live public IP/DNS and adds
   an AWS resource.
6. After host access is restored, capture current disk, swap, kernel/Docker OOM
   events, container peaks, queue depth and backup marker freshness immediately
   before requesting separate stop/start authorization.

## Cost and CPU

- Sydney on-demand compute: `m7i-flex.large` USD 0.1197/hour versus `t3.medium`
  USD 0.0528/hour.
- Expected compute saving at 730 hours: USD 48.84/month (55.9%), about USD
  586/year. EBS, snapshots, public IPv4, S3, transfer and monitoring are separate.
- Observed EC2 CPU since launch: 6.04% average, 7.18% p95, 20.76% highest
  15-minute average, with a short 99.92% sample.
- A `t3.medium` baseline is 20% with 24 credits/hour and a 576-credit maximum.
  Start in Unlimited mode and alarm on `CPUCreditBalance`,
  `CPUSurplusCreditBalance` and `CPUSurplusCreditsCharged`. Current sustained CPU
  is below baseline, but prolonged use above it can add charges.

## Planned maintenance and rollback

After all gates pass and a separate stop/start authorization is received: drain
new uploads briefly, record queues and container state, stop the instance, change
only the instance type to `t3.medium`, set the intended T3 credit mode, start it,
wait for both EC2 status checks, and validate HTTPS, all containers, ClamAV,
synthetic resume processing, queues, memory/OOM state and a verified backup.

Reserve a 30-minute window after Elastic-IP continuity is established. If any
validation fails, stop the instance, change it back to `m7i-flex.large`, start it,
and repeat validation. Do not terminate it or restore an older database over live
writes. Use the pre-resize snapshot only for volume recovery, and restore a
verified logical backup into a separate database/volume before any explicit
switch.
