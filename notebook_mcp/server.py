from mcp.server.fastmcp import FastMCP

import os
import uuid
import base64
import nbformat
import queue

from nbconvert import HTMLExporter, PythonExporter, PDFExporter

from jupyter_client import KernelManager
from io import BytesIO

mcp = FastMCP("notebook-mcp")

# -----------------------------
# Kernel store (per notebook)
# -----------------------------
KERNELS = {}


def load_nb(path):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return nbformat.read(path, as_version=4)


def save_nb(path, nb):
    nbformat.write(nb, path)


def get_kernel(path, kernel_name="python3"):
    if path in KERNELS:
        return KERNELS[path]

    km = KernelManager(kernel_name=kernel_name)
    km.start_kernel()
    kc = km.client()
    kc.start_channels()

    KERNELS[path] = {"km": km, "kc": kc}
    return KERNELS[path]


def run_code(kernel, code, timeout=600):
    kc = kernel["kc"]
    km = kernel["km"]
    
    if not km.is_alive():
        km.restart_kernel()
        kc = km.client()
        kc.start_channels()
        kernel["kc"] = kc
        return [{"type": "error", "ename": "KernelDead", "evalue": "Kernel was dead before execution.", "traceback": ["The kernel was dead and has been auto-restarted. Please run the cell again."]}], None

    kc.execute(code)

    outputs = []
    execution_count = None

    elapsed = 0
    while True:
        try:
            msg = kc.get_iopub_msg(timeout=1)
        except queue.Empty:
            if not km.is_alive():
                km.restart_kernel()
                kc = km.client()
                kc.start_channels()
                kernel["kc"] = kc
                outputs.append({"type": "error", "ename": "KernelCrashed", "evalue": "Kernel crashed during execution.", "traceback": ["The kernel died unexpectedly and was auto-restarted."]})
                break
            
            elapsed += 1
            if elapsed >= timeout:
                outputs.append({"type": "error", "ename": "TimeoutError", "evalue": "Cell execution timed out.", "traceback": [f"Execution exceeded {timeout} seconds."]})
                break
            continue

        msg_type = msg["header"]["msg_type"]
        content = msg["content"]

        if msg_type == "stream":
            outputs.append({"type": "stdout", "text": content["text"]})

        elif msg_type == "execute_result":
            outputs.append({
                "type": "result", 
                "data": content["data"],
                "execution_count": content.get("execution_count")
            })

        elif msg_type == "display_data":
            outputs.append({
                "type": "display_data",
                "data": content["data"]
            })

        elif msg_type == "error":
            outputs.append({
                "type": "error",
                "ename": content["ename"],
                "evalue": content["evalue"],
                "traceback": content.get("traceback", [])
            })

        elif msg_type == "status" and content["execution_state"] == "idle":
            break
        elif msg_type == "execute_input":
            execution_count = content.get("execution_count")

    return outputs, execution_count

def format_outputs(outputs):
    formatted = []
    for out in outputs:
        if out["type"] == "stdout":
            formatted.append(nbformat.v4.new_output("stream", name="stdout", text=out["text"]))
        elif out["type"] == "result":
            formatted.append(nbformat.v4.new_output("execute_result", data=out.get("data", {}), execution_count=out.get("execution_count")))
        elif out["type"] == "display_data":
            formatted.append(nbformat.v4.new_output("display_data", data=out.get("data", {})))
        elif out["type"] == "error":
            formatted.append(nbformat.v4.new_output("error", ename=out.get("ename", ""), evalue=out.get("evalue", ""), traceback=out.get("traceback", [])))
    return formatted


# -----------------------------
# NOTEBOOK OPS
# -----------------------------

@mcp.tool()
def create_notebook(path: str):
    """
    Create a fresh .ipynb file at the given path.
    """
    nb = nbformat.v4.new_notebook()

    nb.cells = []
    nb.metadata = {}

    save_nb(path, nb)

    return {
        "status": "created",
        "path": path
    }

@mcp.tool()
def read_notebook(path: str):
    """
    Read the contents of a notebook and return all its cells.
    """
    nb = load_nb(path)
    return {
        "cells": [
            {"index": i, "type": c.cell_type, "source": c.source}
            for i, c in enumerate(nb.cells)
        ]
    }


@mcp.tool()
def update_cell(path: str, index: int, source: str):
    """
    Update the source code/text of an existing cell at the specified index.
    """
    nb = load_nb(path)
    nb.cells[index].source = source
    save_nb(path, nb)
    return {"status": "updated"}


@mcp.tool()
def insert_cell(path: str, index: int, cell_type: str, source: str):
    """
    Insert a new cell (code or markdown) at the specified index.
    """
    nb = load_nb(path)

    if cell_type == "code":
        cell = nbformat.v4.new_code_cell(source)
    else:
        cell = nbformat.v4.new_markdown_cell(source)

    nb.cells.insert(index, cell)
    save_nb(path, nb)

    return {"status": "inserted"}


@mcp.tool()
def move_cell(path: str, source_index: int, target_index: int):
    """
    Move a cell from source_index to target_index while preserving its contents and outputs.
    """
    nb = load_nb(path)
    
    if source_index < 0 or source_index >= len(nb.cells):
        return {"error": "source_index out of bounds"}
        
    cell = nb.cells.pop(source_index)
    nb.cells.insert(target_index, cell)
    save_nb(path, nb)
    
    return {"status": "moved"}


@mcp.tool()
def delete_cell(path: str, index: int):
    """
    Delete a cell from the notebook at the specified index.
    """
    nb = load_nb(path)
    nb.cells.pop(index)
    save_nb(path, nb)
    return {"status": "deleted"}


@mcp.tool()
def list_cells(path: str):
    """
    List all cells in the notebook, returning their indices and types.
    """
    nb = load_nb(path)
    return [
        {"index": i, "type": c.cell_type}
        for i, c in enumerate(nb.cells)
    ]


# -----------------------------
# EXECUTION
# -----------------------------

@mcp.tool()
def run_cell(path: str, index: int, kernel_name: str = "python3"):
    """
    Execute a specific code cell in the notebook.
    """
    nb = load_nb(path)
    kernel = get_kernel(path, kernel_name)

    cell = nb.cells[index]
    if cell.cell_type != "code":
        return {"error": "not code cell"}

    outputs, exec_count = run_code(kernel, cell.source)
    cell.outputs = format_outputs(outputs)
    if exec_count is not None:
        cell.execution_count = exec_count
    save_nb(path, nb)

    return outputs


@mcp.tool()
def run_all(path: str, kernel_name: str = "python3"):
    """
    Execute all code cells in the notebook sequentially.
    """
    nb = load_nb(path)
    kernel = get_kernel(path, kernel_name)

    results = []
    for i, cell in enumerate(nb.cells):
        if cell.cell_type == "code":
            outputs, exec_count = run_code(kernel, cell.source)
            cell.outputs = format_outputs(outputs)
            if exec_count is not None:
                cell.execution_count = exec_count
            results.append({
                "cell": i,
                "outputs": outputs
            })
    save_nb(path, nb)

    return results


@mcp.tool()
def change_kernel(path: str, display_name: str, kernel_name: str = "python3"):
    """
    Change the notebook's kernelspec metadata to use a different kernel.
    """
    from jupyter_client.kernelspec import KernelSpecManager
    ksm = KernelSpecManager()
    available = ksm.find_kernel_specs()
    if kernel_name not in available:
        return {
            "error": f"Kernel '{kernel_name}' not found.",
            "available_kernels": list(available.keys())
        }

    nb = load_nb(path)
    if "metadata" not in nb:
        nb.metadata = {}
    nb.metadata["kernelspec"] = {
        "display_name": display_name,
        "language": "python",
        "name": kernel_name
    }
    save_nb(path, nb)
    
    if path in KERNELS:
        try:
            KERNELS[path]["km"].shutdown_kernel(now=True)
        except Exception:
            pass
        del KERNELS[path]

    return {"status": "kernel updated", "display_name": display_name, "kernel_name": kernel_name}


@mcp.tool()
def list_kernels():
    """
    List all available Jupyter kernels installed on the system.
    """
    from jupyter_client.kernelspec import KernelSpecManager
    km = KernelSpecManager()
    specs = km.find_kernel_specs()
    
    result = {}
    for name, path in specs.items():
        try:
            spec = km.get_kernel_spec(name)
            result[name] = {
                "display_name": spec.display_name,
                "language": spec.language,
                "path": path
            }
        except Exception:
            result[name] = {"path": path, "error": "Could not load spec"}
    return result


@mcp.tool()
def restart_kernel(path: str):
    """
    Restart the currently running kernel for the notebook.
    """
    if path in KERNELS:
        KERNELS[path]["km"].restart_kernel()
        return {"status": "restarted"}
    return {"error": "no kernel"}


@mcp.tool()
def shutdown_kernel(path: str):
    """
    Shutdown the currently running kernel for the notebook.
    """
    if path in KERNELS:
        KERNELS[path]["km"].shutdown_kernel()
        del KERNELS[path]
        return {"status": "shutdown"}
    return {"error": "no kernel"}


# -----------------------------
# EXPORT SYSTEM
# -----------------------------

@mcp.tool()
def export_html(path: str, out_dir: str = "./exports"):
    """
    Export the notebook to an HTML file.
    """
    nb = load_nb(path)
    os.makedirs(out_dir, exist_ok=True)

    exporter = HTMLExporter()
    body, _ = exporter.from_notebook_node(nb)

    out_path = os.path.join(out_dir, f"{uuid.uuid4()}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(body)

    return {"html": out_path}


@mcp.tool()
def export_python(path: str, out_dir: str = "./exports"):
    """
    Export the notebook to a Python script (.py file).
    """
    nb = load_nb(path)
    os.makedirs(out_dir, exist_ok=True)

    exporter = PythonExporter()
    body, _ = exporter.from_notebook_node(nb)

    out_path = os.path.join(out_dir, f"{uuid.uuid4()}.py")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(body)

    return {"python": out_path}


@mcp.tool()
def export_pdf(path: str, out_dir: str = "./exports"):
    """
    Export the notebook to a PDF file using WebPDF (Playwright).
    """
    nb = load_nb(path)
    os.makedirs(out_dir, exist_ok=True)

    try:
        from nbconvert import WebPDFExporter
        import subprocess
        import sys
        
        # Automatically ensure the headless browser is installed
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False, capture_output=True)

        exporter = WebPDFExporter()
        body, _ = exporter.from_notebook_node(nb)

        out_path = os.path.join(out_dir, f"{uuid.uuid4()}.pdf")
        with open(out_path, "wb") as f:
            f.write(body)

        return {"pdf": out_path}

    except Exception as e:
        return {
            "error": "PDF export failed",
            "reason": str(e),
            "hint": "Ensure playwright and nbconvert[webpdf] are installed."
        }


# -----------------------------
# PLOT EXPORT
# -----------------------------

@mcp.tool()
def export_cell_images(path: str, index: int, out_dir: str = "./exports"):
    """
    Extract and save any images (plots, charts) generated by a specific cell.
    """
    nb = load_nb(path)
    
    if index >= len(nb.cells):
        return {"error": "Cell index out of range"}
        
    cell = nb.cells[index]
    if cell.cell_type != "code":
        return {"error": "Not a code cell"}
        
    os.makedirs(out_dir, exist_ok=True)
    saved_images = []
    
    for output in cell.outputs:
        if "data" in output:
            data = output["data"]
            for mime_type in ["image/png", "image/jpeg"]:
                if mime_type in data:
                    ext = mime_type.split("/")[-1]
                    img_data = base64.b64decode(data[mime_type])
                    img_path = os.path.join(out_dir, f"{uuid.uuid4()}.{ext}")
                    
                    with open(img_path, "wb") as f:
                        f.write(img_data)
                    
                    saved_images.append(img_path)
                    
    return {"images": saved_images}


# -----------------------------
# STATUS
# -----------------------------

@mcp.tool()
def search_cell_source(path: str, query: str):
    """
    Search all cell sources in the notebook for a specific query (case-insensitive).
    Returns a list of matching cells with their index and source text.
    """
    nb = load_nb(path)
    query_lower = query.lower()
    results = []
    for i, cell in enumerate(nb.cells):
        if query_lower in cell.source.lower():
            results.append({
                "index": i,
                "type": cell.cell_type,
                "source": cell.source
            })
    return results


@mcp.tool()
def search_cell_outputs(path: str, query: str):
    """
    Search all cell outputs in the notebook for a specific query (case-insensitive).
    Returns a list of matching cells with their index and the text of the matched outputs.
    """
    nb = load_nb(path)
    query_lower = query.lower()
    results = []
    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "code" or "outputs" not in cell:
            continue
        
        matched_outputs = []
        for out in cell.outputs:
            text = ""
            if out.output_type == "stream":
                text = out.text
            elif out.output_type == "execute_result" and "data" in out and "text/plain" in out.data:
                text = out.data["text/plain"]
            elif out.output_type == "error":
                text = str(out.get("ename", "")) + " " + str(out.get("evalue", "")) + " " + "".join(out.get("traceback", []))
            
            if query_lower in text.lower():
                matched_outputs.append(text)
                
        if matched_outputs:
            results.append({
                "index": i,
                "matched_outputs": matched_outputs
            })
            
    return results


@mcp.tool()
def kernel_status(path: str):
    """
    Check if the kernel for the notebook is currently running.
    """
    if path not in KERNELS:
        return {"status": "not started"}
    return {"status": KERNELS[path]["kc"].is_alive()}


# -----------------------------
# RUN SERVER
# -----------------------------
def main():
    mcp.run()

if __name__ == "__main__":
    main()