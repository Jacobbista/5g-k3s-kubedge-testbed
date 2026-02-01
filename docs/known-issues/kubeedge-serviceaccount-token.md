# KubeEdge ServiceAccount Token Issue

## Problem

Pods running on KubeEdge edge nodes may get stuck in `PodInitializing` state when using the default ServiceAccount token mounting.

**Error in edgecore logs:**
```
serviceaccount.go:112] query meta "default"/"5g"/[]string(nil)/3607/v1.BoundObjectReference... length error
```

## Cause

KubeEdge cannot properly handle Kubernetes **projected ServiceAccount tokens** on edge nodes. The `kube-api-access-*` volume fails to mount, blocking init containers from completing.

## Solution

Disable automatic ServiceAccount token mounting in pod specs:

```yaml
spec:
  automountServiceAccountToken: false
  # ... rest of pod spec
```

This is applied to:
- `gnb-deployment.yaml.j2`
- `ue-statefulset.yaml.j2`

## Additional Issue: Network Interface Race Condition

Even after fixing the ServiceAccount token issue, UERANSIM pods may fail to connect on first start due to Multus network interfaces not being ready when the main container starts.

**Symptoms:**
- gNB process running but no SCTP connections to AMF
- UE process running but no registration
- Works after pod restart

**Solution:**

The `config-gen` init container now waits for network interfaces:

```bash
# Wait for Multus network interfaces to be ready
for i in $(seq 1 30); do
  N2_READY=$(ip addr show n2 2>/dev/null | grep -c "inet " || echo 0)
  if [ "$N2_READY" -gt 0 ]; then
    echo "Network interface ready"
    break
  fi
  sleep 1
done
```

## References

- [KubeEdge Issue #4barbecue - Projected Token Support](https://github.com/kubeedge/kubeedge/issues/)
- [Multus CNI Documentation](https://github.com/k8snetworkplumbingwg/multus-cni)
