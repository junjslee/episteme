# INC-2024-1118 — Autoscaler timeout cascade

**Date:** 2024-11-18
**Severity:** SEV-2
**Duration:** 47 minutes
**Author:** SRE on-call (Marcus L.)

## Summary

p99 latency spiked to 4.2s for ~47 min during the EOD traffic surge. Root-caused to autoscaler timeout: scale-up triggered at 14:32 PT but new pods didn't come online for 23 minutes due to image-pull throttling on the registry. Existing pods at 100% CPU during the gap.

## Root cause (per ticket author)

Autoscaler scale-up latency too high under traffic burst. Recommend reducing image size + warming up the registry mirror.

## Action items

- [ ] Pre-warm registry mirror in us-east-1
- [ ] Reduce base image from 1.2GB → 300MB
- [ ] Add CPU pre-scaler (scale at 70% not 85%)
