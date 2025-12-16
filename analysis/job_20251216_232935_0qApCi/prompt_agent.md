# analyze.task.md

You are inside an isolated container.
Target binary: input.bin

You have access to a Radare2 MCP server with the exact functions listed: list_sessions, list_strings, list_symbols, open_file, open_session, rename_flag, rename_function, run_command, run_javascript, set_comment, set_function_prototype, show_function_details, show_headers, use_decompiler, xrefs_to, disassemble, disassemble_function, get_current_address, get_function_prototype, list_all_strings, list_classes, list_decompilers, list_entrypoints, list_files, list_functions, list_functions_tree, list_imports, list_libraries, list_methods, list_sections, analyze, calculate, close_file, close_session, decompile_function.

Hard rules:

- STATIC analysis only. Do NOT execute the binary.
- Every important claim must include evidence (MCP call + output snippet).
- Prefer dedicated functions (e.g., list_imports, list_strings, decompile_function, disassemble_function).
- Use run_command for raw radare2 commands not covered by dedicated functions (e.g., "aaa", "pdg?", "s sym.main", "afn new_name addr").
- Do NOT use shell pipelines or redirections in run_command (e.g., avoid `| head`, `| grep`, `> file`). radare2 commands are not a shell; pipes can hang. If you need filtering, use radare2's `~` filter (e.g., `afl~main`) or post-process/truncate the output in the written report.
- Focus on security: entrypoint, arg parsing (BOF/SOF risks), help menu, web servers, file ops, system calls.

Deliverable:

- Write a Markdown report to: `report.md`

## Objective (minimum)

1) Analyze for security: entrypoint, params, help, arg parsing vulns, servers, file/system calls.
2) Report: commands timeline, ID, entry/main, decompiles, security insights.

## Decompilation Flow

Given a binary or/and a target function (name or address), produce:

1. **RAW** decompilation output: exactly what r2ghidra prints, unmodified
2. **CLEAN** decompilation: same logic, but made readable with renames and comments

### Inputs

- Binary path: `<BIN_PATH>`
- Function identifier:
  - Name: `<FUNC_NAME>` or
  - Address: `<FUNC_ADDR>` (hex)
- Optional context: `<CONTEXT>`

### Required workflow

1. Open the binary in radare2 and run analysis:
   - Run `aaa` (or equivalent full analysis).
2. Locate the function:
   - If `<FUNC_ADDR>` is provided, seek to it: `s <FUNC_ADDR>`
   - If `<FUNC_NAME>` is provided, search or jump to it, for example:
     - `afl~<FUNC_NAME>` to find it, then `s <addr>` or `s <flag>`
3. Ensure the current seek is inside the target function:
   - Run `af` to (re)analyze the current function if needed.
4. Extract the RAW decompile:
   - Run `pdg` and capture the output as the RAW block.
   - Do not alter spacing, names, or formatting.
5. Generate the CLEAN version:
   - Use the RAW as the only source of truth for control flow and expressions.
   - Keep behavior identical, do not fix bugs or remove checks.
6. Provide a rename map and quick notes.

### Output format (strict)

#### Function: <resolved name and address>

#### RAW decompile (exact r2ghidra output)
```c
<PASTE EXACT OUTPUT OF `pdg` HERE, NO EDITS>
```

#### CLEAN decompile (refactored for readability, same logic)
Rules:

- Rename variables like `var1`, `iVar2`, `uVar3`, `param_1` to meaningful names.
- Rename helper functions if you can infer intent, otherwise keep the original name or use `unk_*`.
- Add short comments for:
  - input validation and bounds checks
  - parsing, serialization, crypto, IO
  - error handling paths and return codes
  - state machine transitions
- Use consistent naming:
  - pointers: `ptr_*`
  - lengths: `*_len`
  - counts: `*_count`
  - status: `status`, `rc`, `err`
- If you cannot infer meaning, use `unk_*` and add a comment explaining what is known.

```c
<PASTE CLEAN VERSION HERE>
```

#### Renaming map
Provide a list of renames with one line of justification for each important rename.

Example:

- `param_1 -> ctx` (passed through multiple calls as a shared context pointer)
- `iVar2 -> packet_len` (used in comparisons and as a memcpy length)

#### Notes
3 to 8 bullets:

- High level purpose of the function
- Inputs, outputs, and side effects
- Key branches or error codes
- Potential security issues if they are obvious from the code


## Step-by-step plan

### 0) Setup and analysis

1) Open de target binary using `radare2_open_file` with the absolute file path `{"file_path":"/workspace/input.bin"}`
2) Set `radare2_use_decompiler` to `pdg` the Ghidra decompiler (pdg)
3) Execute `radare2_analyze` {"level":4}
4) Decompile main function

Record any errors.

### 1) Basic identification

- show_headers {}  // Headers, arch, format
- list_sections {}  // Sections
- list_symbols {}  // Symbols, check stripped (few symbols?)
- list_entrypoints {}  // Entry points, main if present

### 2) Libraries, imports, strings (security focus)

- list_libraries {}  // Linked libs (e.g., libcurl for network?)
- list_imports {}  // Imports (search for socket, bind, listen, fopen, system, execve, scanf, strcpy – potential vulns)
- list_strings {"filter":"-h|--help|usage|password|flag|http|server|port|file|system|exec"}  // Help menu, secrets, network, files
- If more needed: list_all_strings {"filter":"getopt|argc|argv|strcpy|scanf|socket|bind|listen|send|recv|fopen|open|system|execve|popen"}  // Arg parsing, vulns, network, files, cmds

Highlight security-relevant: potential help (-h), unsafe funcs (strcpy → BOF), network (socket → server?), files/system.

### 3) Find entrypoint and main

- list_entrypoints {}  // Get entry0, main if sym.main
- If main not in symbols: list_functions {} and filter for "main"
- Or: run_command {"command":"afl ~main"}  // Find functions with "main"
- Seek to main: run_command {"command":"s sym.main"} or address from above.
- If no main: Seek to entry0 via run_command {"command":"s entry0"}, then disassemble_function {} to view entry, identify calls to __libc_start_main or user main.
- Use xrefs_to {"address":"entry0"} to find calls from entry (pick likely main).
Record address and method.

Analyze params: In main decompile, check for argc/argv (int main(int, char**)), getopt loops.

### 4) Decompile main (Ghidra priority, security lens)

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

### 5) Security hardening and behavior

- run_command {"command":"i~pie,nx,relro,canary,stripped"}  // PIE, NX, RELRO, Canary (__stack_chk_fail import?), stripped
- Vulns inference:
  - xrefs_to on unsafe imports (e.g., {"address":"sym.imp.strcpy"} – check if used in arg parsing)
  - Network: If socket imports, xrefs_to to see bind/listen/send – potential server.
  - Files: xrefs_to fopen/open – check modes, user-controlled paths.
  - System: xrefs_to system/execve/popen – tainted input? Command injection risk.
  - Help menu: xrefs_to "-h" strings – decompile that path.
Summarize: PIE/NX/RELRO/Canary presence, potential vulns (BOF in parsing, etc.).

### 6) Write the report

Write `report.md` with:

---
# Binary Analysis Report

## 1. Identification (format, arch, symbols, stripped?)

## 2. Entry points and main (address, discovery method, params/argc/argv)

## 3. Libraries and imports (security-relevant: unsafe funcs, network, files, system)

## 4. Strings highlights (help menu, secrets, network indicators)

## 5. Decompilation of main

## 6. Security hardening (PIE/NX/RELRO/Canary)

## 7. Potential vulnerabilities (arg parsing BOF/SOF, server setup, file ops, system calls – evidence-based)

## 8. High-level behavior (inferred: accepts params? Help menu? Starts server? Sends data? Opens files? Calls binaries?)

## 9. Next steps (static: more decompiles, xrefs on suspects)

---

- close_file {}  // Cleanup

Now produce `report.md` following this plan strictly
