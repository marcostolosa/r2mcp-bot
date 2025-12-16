# analyze.task.md

You are inside an isolated container.
Target binary: /workspace/input.bin

You have access to a Radare2 MCP server with the exact functions listed: list_sessions, list_strings, list_symbols, open_file, open_session, rename_flag, rename_function, run_command, run_javascript, set_comment, set_function_prototype, show_function_details, show_headers, use_decompiler, xrefs_to, disassemble, disassemble_function, get_current_address, get_function_prototype, list_all_strings, list_classes, list_decompilers, list_entrypoints, list_files, list_functions, list_functions_tree, list_imports, list_libraries, list_methods, list_sections, analyze, calculate, close_file, close_session, decompile_function.

Hard rules:
- STATIC analysis only. Do NOT execute the binary.
- Every important claim must include evidence (MCP call + output snippet).
- Prefer dedicated functions (e.g., list_imports, list_strings, decompile_function, disassemble_function).
- Use run_command for raw radare2 commands not covered by dedicated functions (e.g., "aaa", "pdg?", "s sym.main", "afn new_name addr").
- Do NOT use shell pipelines or redirections in run_command (e.g., avoid `| head`, `| grep`, `> file`). radare2 commands are not a shell; pipes can hang. If you need filtering, use radare2's `~` filter (e.g., `afl~main`) or post-process/truncate the output in the written report.
- Focus on security: entrypoint, arg parsing (BOF/SOF risks), help menu, web servers, file ops, system calls.

Deliverable:
- Write a Markdown report to: /workspace/report.md

## Objective (minimum)
1) Force Ghidra decompiler (pdg) if available, decompile main.
2) Analyze for security: entrypoint, params, help, arg parsing vulns, servers, file/system calls.
3) Report: commands timeline, ID, entry/main, decompiles, security insights.

## Step-by-step plan

### 0) Setup and analysis
- open_file {"file_path":"/workspace/input.bin"}
- analyze {"level":3}  // Deep analysis, equivalent to aaa

Record any errors.

### 1) Verify Ghidra decompiler
- list_decompilers {}  // Check if ghidra/pdg available
- If "ghidra" or "pdg" in list: use_decompiler {"name":"pdg"} or {"name":"ghidra"}
- Fallback verify: run_command {"command":"pdg?"}
  - If help/usage: pdg available.
  - Else: run_command {"command":"pdc?"} for fallback, or disassemble_function as last resort.
Record availability.

### 2) Basic identification
- show_headers {}  // Headers, arch, format
- list_sections {}  // Sections
- list_symbols {}  // Symbols, check stripped (few symbols?)
- list_entrypoints {}  // Entry points, main if present

### 3) Libraries, imports, strings (security focus)
- list_libraries {}  // Linked libs (e.g., libcurl for network?)
- list_imports {}  // Imports (search for socket, bind, listen, fopen, system, execve, scanf, strcpy – potential vulns)
- list_strings {"filter":"-h|--help|usage|password|flag|http|server|port|file|system|exec"}  // Help menu, secrets, network, files
- If more needed: list_all_strings {"filter":"getopt|argc|argv|strcpy|scanf|socket|bind|listen|send|recv|fopen|open|system|execve|popen"}  // Arg parsing, vulns, network, files, cmds

Highlight security-relevant: potential help (-h), unsafe funcs (strcpy → BOF), network (socket → server?), files/system.

### 4) Find entrypoint and main
- list_entrypoints {}  // Get entry0, main if sym.main
- If main not in symbols: list_functions {} and filter for "main"
- Or: run_command {"command":"afl ~main"}  // Find functions with "main"
- Seek to main: run_command {"command":"s sym.main"} or address from above.
- If no main: Seek to entry0 via run_command {"command":"s entry0"}, then disassemble_function {} to view entry, identify calls to __libc_start_main or user main.
- Use xrefs_to {"address":"entry0"} to find calls from entry (pick likely main).
Record address and method.

Analyze params: In main decompile, check for argc/argv (int main(int, char**)), getopt loops.

### 5) Decompile main (Ghidra priority, security lens)
- Seek to main if not already: run_command {"command":"s sym.main"}
- Raw decompile:
  - If pdg set: decompile_function {"address":"sym.main"} or current via get_current_address
  - Fallback: run_command {"command":"pdc"} or disassemble_function {}
- Capture output in ```c block.

Cleaned decompile:
- Identify called funcs: list_functions_tree {} or xrefs_to on main address (calls to?).
- Rename based on evidence: e.g., if calls strcmp on "password" string: rename_function {"address":"0xADDR", "name":"check_password"}
- Re-decompile after renames.
- Format manually: indent, comments on security (e.g., // Potential BOF: unsafe strcpy, // Parses args with getopt – check for overflow, // Opens file without checks, // Calls system() with user input?).
- Look for: Arg parsing loops (getopt/strcmp – BOF if no bounds), help menu (if "-h" string xref to printf), server (socket/bind/listen sequences), file ops (fopen xrefs), system calls (system/execve with tainted input).

### 6) Security hardening and behavior
- run_command {"command":"i~pie,nx,relro,canary,stripped"}  // PIE, NX, RELRO, Canary (__stack_chk_fail import?), stripped
- Vulns inference:
  - xrefs_to on unsafe imports (e.g., {"address":"sym.imp.strcpy"} – check if used in arg parsing)
  - Network: If socket imports, xrefs_to to see bind/listen/send – potential server.
  - Files: xrefs_to fopen/open – check modes, user-controlled paths.
  - System: xrefs_to system/execve/popen – tainted input? Command injection risk.
  - Help menu: xrefs_to "-h" strings – decompile that path.
Summarize: PIE/NX/RELRO/Canary presence, potential vulns (BOF in parsing, etc.).

### 7) Write the report
Write /workspace/report.md with:

# Binary Analysis Report
## 1. Timeline of MCP calls (with key outputs/snippets)
## 2. Identification (format, arch, symbols, stripped?)
## 3. Entry points and main (address, discovery method, params/argc/argv)
## 4. Libraries and imports (security-relevant: unsafe funcs, network, files, system)
## 5. Strings highlights (help menu, secrets, network indicators)
## 6. Decompilation of main
### 6.1 Raw decompile
### 6.2 Cleaned decompile (renamed, formatted, security comments)
## 7. Security hardening (PIE/NX/RELRO/Canary)
## 8. Potential vulnerabilities (arg parsing BOF/SOF, server setup, file ops, system calls – evidence-based)
## 9. High-level behavior (inferred: accepts params? Help menu? Starts server? Sends data? Opens files? Calls binaries?)
## 10. Next steps (static: more decompiles, xrefs on suspects)

- close_file {}  // Cleanup

Now produce /workspace/report.md following this plan strictly.


