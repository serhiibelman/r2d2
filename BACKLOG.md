# Backlog

Work that is understood but not done. Ordered by what hurts most if it stays
undone, not by effort. Each item says why it matters and where it lands, so
picking one up does not mean rediscovering the problem.

Repos: `r2d2` (this one, the vehicle) and `r2d2-infrastructure` (AWS).

---

## 1. Offline telemetry spool

**Where:** `lib/telemetry/`, new `lib/spool/` · **Size:** M

Today a publish that fails is logged and dropped. Every message sent while the
uplink is down is gone - which is most of the interesting ones, because losing
the link is exactly when something is going wrong.

Write telemetry to a local SQLite file first, flush to MQTT on reconnect, mark
rows sent. SQLite is stdlib, single file, survives power loss mid-drive. Cap
retention (ring buffer or delete-after-N-days): a full SD card takes the whole
vehicle down.

Deferred deliberately when the publisher was built - "plain publish first".

## 2. Battery and attitude telemetry

**Where:** `apps/vehicle_control/fc.py`, `apps/api/services/vehicle_status.py` · **Size:** S

Battery is the single most useful field on any vehicle: it predicts the failure
that actually strands it. `SYS_STATUS` over MAVLink carries `voltage_battery`,
`current_battery` and `battery_remaining`, and nothing reads it yet.

`fc.py` already reads `ATTITUDE` (roll/pitch/yaw) and throws it away. Getting it
into the snapshot is nearly free and gives tipped/stuck detection.

Both flow to Postgres automatically once they are in `snapshot()` - the payload
is JSONB, so no schema change is needed.

## 3. Last Will and Testament

**Where:** `lib/telemetry/publisher.py` (`_PahoConnection.connect`) · **Size:** XS

Register an "offline" message at connect time and the broker publishes it the
instant the connection drops - including on power loss, where the Pi gets no
chance to say anything. Today offline is inferred from missing heartbeats,
which with the 300s idle interval means up to five minutes of ambiguity.

`client.will_set(topic=f"rover/{thing}/status", payload="offline", retain=True)`,
plus publishing `online` after connect. Retained, so anything subscribing later
sees current state immediately.

## 4. Scope the IoT policy

**Where:** `r2d2-infrastructure/terraform/iot.tf` · **Size:** S

`aws_iot_policy.rover` grants Connect/Publish/Subscribe on `Resource = "*"`.
Any device certificate can connect under any client ID and read every rover's
topics, which throws away the main reason for per-device certificates: a stolen
rover becomes a fleet-wide listener.

```hcl
Resource = "arn:aws:iot:${region}:${account}:client/$${iot:Connection.Thing.ThingName}"
Resource = "arn:aws:iot:${region}:${account}:topic/rover/$${iot:Connection.Thing.ThingName}/telemetry"
```

Cheap with one rover, painful to retrofit across a fleet.

## 5. Raspberry Pi health telemetry

**Where:** `apps/api/services/vehicle_status.py` · **Size:** S

CPU temperature, load, free RAM, free disk, and the undervoltage/throttling flag
(`vcgencmd get_throttled`). On a Pi 1 these predict most field failures:
thermal throttling, a full SD card, a weak USB supply browning out the board.

Cheap to collect, and they explain failures that otherwise look like random
hangs.

## 6. Control-link failsafe

**Where:** `apps/vehicle_control/vehicle_controller.py` · **Size:** S

`run()` only acts when a packet arrives:

```python
state = self._receive_latest()
if state is not None:
    self._handle(state)
time.sleep(LOOP_INTERVAL)
```

With no packet it sleeps and loops, so the motors hold their last commanded
RPM. If the laptop sleeps, Wi-Fi drops, or the controller process dies
mid-drive, the rover keeps going at that speed indefinitely. `_stop_motors()`
runs only on `KeyboardInterrupt`, which never fires when the *link* dies rather
than the process.

Track the time of the last accepted packet; past a timeout (~0.5s) stop the
motors and drop `_drive_enabled` until a fresh packet arrives. Packets already
carry a `timestamp` field that is parsed and never used.

Deferred by choice, not oversight - worth doing before the rover drives
anywhere it could hurt something.

---

## Infrastructure

### Terraform state in S3

**Where:** `r2d2-infrastructure/terraform/terraform.tf` · **Size:** S

State is a local file on one machine. Only that machine can run terraform, and
losing the file means terraform forgets it owns the VPC, RDS and IoT thing -
recovery is `terraform import` on every resource by hand. It also holds the
database password in clear text.

An S3 backend with `encrypt = true`, bucket versioning and `use_lockfile = true`
fixes all three. The bucket must exist first, then `terraform init
-migrate-state`.

### A way to query the database

**Where:** `r2d2-infrastructure/terraform/` · **Size:** M

`rover-db` is private and RDS has no table browser in the console, so there is
no way to run SQL against it today. The Lambda's `{"stats": true}` mode covers
"is data arriving"; it does not cover anything else.

An SSM bastion (t4g.nano, IAM role, no inbound ports) plus port forwarding gives
`psql`/DBeaver access, and is also what migrations would run through.

### Database password in Secrets Manager

**Where:** `r2d2-infrastructure/terraform/lambda.tf` · **Size:** S

`var.db_password` is passed to the Lambda as a plain environment variable,
visible to anyone with console access to the function. Secrets Manager with
rotation is the upgrade.

### Harden the RDS instance

**Where:** `r2d2-infrastructure/terraform/database.tf` · **Size:** S

`skip_final_snapshot = true`, no `storage_encrypted`, no backup retention, no
deletion protection. Fine for a prototype; revisit before anything is stored
that would hurt to lose.

---

## Housekeeping

- **`start_api.sh` venv mismatch** - sources `.venv-3.12`, the README uses
  `venv`. Whichever is right, they should agree.
- **Telemetry only publishes from the API process.** `start_vehicle.sh` runs
  `apps.vehicle_control.main`, which has no publisher, so driving without the
  API sends nothing. Either document it or move the publisher.
- **Three files fail `black`** - `apps/api/services/camera.py`,
  `apps/api/services/vehicle_status.py`,
  `apps/vehicle_control/vehicle_controller.py`. Pre-existing.
- **`tests/test_camera_service.py` reads real env vars,** so it fails whenever a
  `.env` exists with non-default camera values. Tests should not depend on the
  machine they run on.
- **No CI.** A GitHub Action running `pytest` and `black --check` would have
  caught both of the above.
- **Lambda logs nothing on success,** so "it worked" is inferred from the
  absence of a traceback.

## If the fleet grows past one rover

Not needed now; the numbers change at scale.

- **Batch telemetry** into one message per window rather than per sample - IoT
  Core bills per message.
- **RDS Proxy** in front of Postgres: one Lambda invocation per message means
  Lambda concurrency, not Postgres, hits the connection limit first.
- **Archive raw telemetry to S3** via a second IoT rule and keep only recent
  data in Postgres - roughly 5x cheaper per GB.
- **Reconsider Postgres** for high-rate sensor streams: state and events belong
  in Postgres, continuous 100 Hz data does not.
