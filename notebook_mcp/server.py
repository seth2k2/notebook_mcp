from mcp.server.fastmcp import FastMCP

import os
import uuid
import nbformat

from nbconvert import HTMLExporter, PythonExporter, PDFExporter

from jupyter_client import KernelManager
import matplotlib.pyplot as plt
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


def run_code(kernel, code, timeout=60):
    kc = kernel["kc"]
    kc.execute(code)

    outputs = []

    while True:
        msg = kc.get_iopub_msg(timeout=timeout)
        msg_type = msg["header"]["msg_type"]
        content = msg["content"]

        if msg_type == "stream":
            outputs.append({"type": "stdout", "text": content["text"]})

        elif msg_type == "execute_result":
            outputs.append({"type": "result", "data": content["data"]})

        elif msg_type == "error":
            outputs.append({
                "type": "error",
                "ename": content["ename"],
                "evalue": content["evalue"]
            })

        elif msg_type == "status" and content["execution_state"] == "idle":
            break

    return outputs


# -----------------------------
# NOTEBOOK OPS
# -----------------------------

@mcp.tool()
def create_notebook(path: str):
    """
    Create a fresh .ipynb file
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
    nb = load_nb(path)
    return {
        "cells": [
            {"index": i, "type": c.cell_type, "source": c.source}
            for i, c in enumerate(nb.cells)
        ]
    }


@mcp.tool()
def update_cell(path: str, index: int, source: str):
    nb = load_nb(path)
    nb.cells[index].source = source
    save_nb(path, nb)
    return {"status": "updated"}


@mcp.tool()
def insert_cell(path: str, index: int, cell_type: str, source: str):
    nb = load_nb(path)

    if cell_type == "code":
        cell = nbformat.v4.new_code_cell(source)
    else:
        cell = nbformat.v4.new_markdown_cell(source)

    nb.cells.insert(index, cell)
    save_nb(path, nb)

    return {"status": "inserted"}


@mcp.tool()
def delete_cell(path: str, index: int):
    nb = load_nb(path)
    nb.cells.pop(index)
    save_nb(path, nb)
    return {"status": "deleted"}


@mcp.tool()
def list_cells(path: str):
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
    nb = load_nb(path)
    kernel = get_kernel(path, kernel_name)

    cell = nb.cells[index]
    if cell.cell_type != "code":
        return {"error": "not code cell"}

    return run_code(kernel, cell.source)


@mcp.tool()
def run_all(path: str, kernel_name: str = "python3"):
    nb = load_nb(path)
    kernel = get_kernel(path, kernel_name)

    results = []
    for i, cell in enumerate(nb.cells):
        if cell.cell_type == "code":
            results.append({
                "cell": i,
                "outputs": run_code(kernel, cell.source)
            })

    return results


@mcp.tool()
def restart_kernel(path: str):
    if path in KERNELS:
        KERNELS[path]["km"].restart_kernel()
        return {"status": "restarted"}
    return {"error": "no kernel"}


@mcp.tool()
def shutdown_kernel(path: str):
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
    nb = load_nb(path)
    os.makedirs(out_dir, exist_ok=True)

    try:
        exporter = PDFExporter()
        body, _ = exporter.from_notebook_node(nb)

        out_path = os.path.join(out_dir, f"{uuid.uuid4()}.pdf")
        with open(out_path, "wb") as f:
            f.write(body)

        return {"pdf": out_path}

    except Exception as e:
        return {
            "error": "PDF export failed",
            "reason": str(e),
            "hint": "install latex or use HTML export"
        }


# -----------------------------
# PLOT EXPORT
# -----------------------------

@mcp.tool()
def export_last_plot(out_dir: str = "./exports"):
    os.makedirs(out_dir, exist_ok=True)

    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)

    path = os.path.join(out_dir, f"{uuid.uuid4()}.png")

    with open(path, "wb") as f:
        f.write(buf.getvalue())

    return {"image": path}


# -----------------------------
# STATUS
# -----------------------------

@mcp.tool()
def kernel_status(path: str):
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