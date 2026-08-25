"""
gpu_check.py - Verify Blender is actually going to use the GPU.

Run this FIRST on any new machine (RunPod, Colab, local) before starting a
long render. Renders on a GPU pod silently falling back to CPU is the most
expensive failure mode in this pipeline: it bills GPU rates for CPU speed.

Usage:
    blender -b -P src/gpu_check.py

Exit code is 0 when a hardware GPU path is confirmed, 1 otherwise, so it can
gate a render in a shell script:

    blender -b -P src/gpu_check.py && ./run_all.sh --quality high
"""

import sys

try:
    import bpy
except ImportError:
    print("✗ This script must be run inside Blender:")
    print("    blender -b -P src/gpu_check.py")
    sys.exit(1)


def check_cycles_devices():
    """Report Cycles compute devices available on this machine."""
    print("\n" + "=" * 60)
    print("CYCLES COMPUTE DEVICES")
    print("=" * 60)

    try:
        cprefs = bpy.context.preferences.addons['cycles'].preferences
    except (AttributeError, KeyError) as e:
        print(f"⚠ Cycles preferences unavailable: {e}")
        return False

    found_any = False
    for backend in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL'):
        try:
            cprefs.compute_device_type = backend
        except (TypeError, AttributeError):
            print(f"  {backend:<8} not supported by this build")
            continue

        try:
            devices = cprefs.get_devices_for_type(backend)
        except (AttributeError, TypeError):
            try:
                cprefs.get_devices()
                devices = [d for d in cprefs.devices if d.type == backend]
            except Exception:
                devices = []

        if devices:
            found_any = True
            print(f"  {backend:<8} AVAILABLE")
            for d in devices:
                print(f"             · {d.name}")
        else:
            print(f"  {backend:<8} no devices")

    if not found_any:
        print("\n✗ No GPU compute devices visible to Cycles.")
        print("  On RunPod check that the container exposes the GPU:")
        print("    nvidia-smi")
    return found_any


def check_eevee_context():
    """
    Report the GPU context Blender is running under.

    This is the number that matters for EEVEE Next: a software rasterizer
    (llvmpipe/swrast) means EEVEE runs on CPU no matter what GPU is present.
    """
    print("\n" + "=" * 60)
    print("EEVEE / OPENGL CONTEXT")
    print("=" * 60)

    try:
        import gpu
        renderer = str(gpu.platform.renderer_get())
        vendor = str(gpu.platform.vendor_get())
        version = str(gpu.platform.version_get())
    except Exception as e:
        print(f"⚠ Could not query GPU context: {e}")
        print("  Blender may be running without any GL context at all.")
        return False

    print(f"  Renderer: {renderer}")
    print(f"  Vendor:   {vendor}")
    print(f"  Version:  {version}")

    software_markers = ('llvmpipe', 'softpipe', 'swrast', 'software', 'mesa offscreen')
    is_software = any(m in renderer.lower() for m in software_markers)

    if is_software:
        print("\n✗ SOFTWARE rasterizer — EEVEE will render on the CPU.")
        print("  This is what happens under `xvfb-run`.")
        print("  Fix: launch Blender with an EGL context instead:")
        print("      export BLENDER_ENABLE_EGL=1")
        print("      blender -b ...        (no xvfb-run wrapper)")
        print("  The container needs libEGL + the NVIDIA EGL vendor ICD.")
        return False

    print("\n✓ Hardware GPU context — EEVEE will use the GPU.")
    return True


def main():
    print("\n" + "=" * 60)
    print("iavideoNubeYT — GPU READINESS CHECK")
    print("=" * 60)
    print(f"Blender: {bpy.app.version_string}")

    cycles_ok = check_cycles_devices()
    eevee_ok = check_eevee_context()

    print("\n" + "=" * 60)
    print("VERDICT")
    print("=" * 60)
    print(f"  Cycles GPU available : {'YES' if cycles_ok else 'NO'}")
    print(f"  EEVEE hardware GPU   : {'YES' if eevee_ok else 'NO'}")

    if eevee_ok:
        print("\n✓ Ready: this pipeline (EEVEE Next) will render on the GPU.")
        code = 0
    elif cycles_ok:
        print("\n⚠ Cycles sees the GPU but EEVEE does not have a hardware context.")
        print("  The pipeline uses EEVEE Next, so it would still render on CPU.")
        print("  Fix the EGL context before starting a long render.")
        code = 1
    else:
        print("\n✗ No GPU path available. A long render here will be CPU-bound.")
        code = 1

    print("=" * 60 + "\n")
    sys.exit(code)


if __name__ == "__main__":
    main()
