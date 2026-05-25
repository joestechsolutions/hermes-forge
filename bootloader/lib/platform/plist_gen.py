"""
launchd plist generator for macOS services.

Converts Hermes service definitions into macOS launchd plist XML.
"""

import os
from typing import Optional


def generate_plist(
    label: str,
    command: str,
    working_directory: str,
    environment: Optional[dict] = None,
    keep_alive: bool = True,
    run_at_load: bool = True,
    standard_out_path: str = "/tmp/hermes-%label%.log",
    standard_err_path: str = "/tmp/hermes-%label%-err.log",
    restart_interval: int = 10,
) -> str:
    """
    Generate a launchd plist XML string for a Hermes service.

    Args:
        label: Launchd label (e.g., "com.hermes.gateway")
        command: Full path to executable plus args (as a single string or list)
        working_directory: Working directory for the process
        environment: Dict of env vars
        keep_alive: Auto-restart on crash
        run_at_load: Start when plist is loaded
        standard_out_path: stdout log path (%label% replaced with label)
        standard_err_path: stderr log path
        restart_interval: Seconds to wait before restart

    Returns:
        Plist XML string
    """
    if environment is None:
        environment = {}

    label_safe = label.replace("com.hermes.", "")
    out_path = standard_out_path.replace("%label%", label_safe)
    err_path = standard_err_path.replace("%label%", label_safe)

    # Build ProgramArguments from command
    if isinstance(command, str):
        program_arguments = command.split()
    else:
        program_arguments = command
    program = program_arguments[0]
    program_args = program_arguments[1:]

    # Build EnvironmentVariables dict
    env_xml = ""
    for key, val in sorted(environment.items()):
        env_xml += f"        <key>{_xml_escape(key)}</key>\n"
        env_xml += f"        <string>{_xml_escape(val)}</string>\n"

    args_xml = ""
    for arg in program_args:
        args_xml += f"        <string>{_xml_escape(arg)}</string>\n"

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_xml_escape(label)}</string>

    <key>Program</key>
    <string>{_xml_escape(program)}</string>
"""
    if program_args:
        plist += """    <key>ProgramArguments</key>
    <array>
""" + args_xml + """    </array>
"""

    plist += f"""    <key>WorkingDirectory</key>
    <string>{_xml_escape(working_directory)}</string>
"""
    if env_xml:
        plist += """    <key>EnvironmentVariables</key>
    <dict>
""" + env_xml + """    </dict>
"""

    plist += f"""    <key>KeepAlive</key>
    <{str(keep_alive).lower()}/>

    <key>RunAtLoad</key>
    <{str(run_at_load).lower()}/>

    <key>StandardOutPath</key>
    <string>{_xml_escape(out_path)}</string>

    <key>StandardErrorPath</key>
    <string>{_xml_escape(err_path)}</string>

    <key>ThrottleInterval</key>
    <integer>{restart_interval}</integer>
</dict>
</plist>
"""
    return plist


def _xml_escape(s: str) -> str:
    """Escape special XML characters."""
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    s = s.replace('"', "&quot;")
    s = s.replace("'", "&apos;")
    return s