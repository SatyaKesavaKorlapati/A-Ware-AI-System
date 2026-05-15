import importlib.metadata

print("\n" + "="*50)
print("🔍 PACKAGE DEPENDENCY INSPECTOR 🔍")
print("="*50)

packages_to_check = ['isaacsim-core', 'isaacsim-robot', 'numpy', 'scipy', 'osqp', 'torch']

for pkg in packages_to_check:
    try:
        version = importlib.metadata.version(pkg)
        requires = importlib.metadata.requires(pkg)
        print(f"\n📦 {pkg.upper()} (Installed v{version})")
        
        found_relevant = False
        if requires:
            for req in requires:
                # Filter to only show the conflict-prone libraries
                req_lower = req.lower()
                if any(x in req_lower for x in ['numpy', 'scipy', 'osqp', 'torch']):
                    print(f"  ↳ STRICT REQUIREMENT: {req}")
                    found_relevant = True
            
        if not found_relevant:
            print("  ↳ No strict math/torch requirements explicitly listed.")
            
    except importlib.metadata.PackageNotFoundError:
        print(f"\n❌ {pkg.upper()} --- NOT INSTALLED")

print("\n" + "="*50)