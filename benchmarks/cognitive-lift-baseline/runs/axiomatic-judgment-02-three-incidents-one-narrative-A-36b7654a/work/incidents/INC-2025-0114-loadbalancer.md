# INC-2025-0114 — Load balancer connection exhaustion

**Date:** 2025-01-14
**Severity:** SEV-2
**Duration:** 52 minutes
**Author:** SRE on-call (Tomás R.)

## Summary

p99 latency spiked to 4.5s for ~52 min. CPU and memory on app pods normal; DNS resolver healthy. dmesg on the LB nodes showed `nf_conntrack: table full, dropping packet` — the conntrack table on the L4 load-balancer hosts (running iptables/netfilter) hit the configured 524288 limit during the traffic surge. New connections dropped at the kernel level before reaching app code.

## Root cause (per ticket author)

Insufficient conntrack table size on LB hosts. Default kernel limit was never tuned for our connection volume.

## Action items

- [ ] Bump nf_conntrack_max from 524288 → 2097152 on LB hosts
- [ ] Tune nf_conntrack_tcp_timeout_established (default 5 days → 12h)
- [ ] Add Prometheus alert on `node_nf_conntrack_entries / node_nf_conntrack_entries_limit > 0.8`
