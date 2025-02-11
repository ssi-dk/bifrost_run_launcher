import sys
#!/usr/bin/env python3
launcher_dir = "/home/projects/fvst_ssi_dtu/apps/sofi_bifrost_dev/scripts/bifrost/components/bifrost_run_launcher/bifrost_run_launcher"
sys.path.append(launcher_dir)
import launcher

print(f"Using launcher.py from: {launcher.__file__}\n")

if __name__ == '__main__':
    launcher.main()
