# Hi, I’m Seniru Epasinghe 👋

I’m an AI undergraduate and an AI enthusiast, working on machine learning projects and open-source contributions.  
I enjoy exploring AI pipelines, natural language processing, and building tools that make development easier.

## 🌐 Connect with me

[![Hugging Face](https://img.shields.io/badge/Hugging%20Face-seniruk-orange?logo=huggingface&logoColor=white)](https://huggingface.co/seniruk) &nbsp;&nbsp;
[![Medium](https://img.shields.io/badge/Medium-seniruk_epasinghe-black?logo=medium&logoColor=white)](https://medium.com/@senirukepasinghe) &nbsp;&nbsp;
[![LinkedIn](https://img.shields.io/badge/LinkedIn-seniru_epasinghe-blue?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/seniru-epasinghe-b34b86232/) &nbsp;&nbsp;
[![GitHub](https://img.shields.io/badge/GitHub-seth2k2-181717?logo=github&logoColor=white)](https://github.com/seth2k2)

---

# 📓 Notebook MCP Server

A **Model Context Protocol (MCP) server** that enables AI tools (like Antigravity, Claude Desktop, etc.) to:

- 🧠 Read and edit Jupyter notebooks (`.ipynb`)
- ⚡ Execute notebook cells with persistent kernel state
- 📊 Capture outputs (text, errors, plots)
- 📁 Create and modify notebooks programmatically
- 📤 Export notebooks to HTML, Python, and PDF
- 🖼 Export plots and visual outputs

This effectively turns your AI assistant into a **Colab-like notebook controller**.

---

# 🚀 Features

- Create new notebooks from scratch
- Read / update / insert / delete cells
- Run single or all cells
- Persistent Python kernel per notebook
- Export:
  - HTML report
  - Python script
  - PDF (if LaTeX installed)
- Capture matplotlib plots as images

---

# ⚙️ Installation

## 🥇 Option 1 — Recommended (uvx / no setup hassle)

This is the easiest way. It automatically creates an isolated environment and runs the server.

### MCP Configuration

Add this to your MCP settings:

```json
{
  "mcpServers": {
    "notebook": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/seth2k2/notebook_mcp.git",
        "notebook-mcp"
      ]
    }
  }
}

## 🚀 What this does (uvx method)

- Downloads the repo automatically
- Creates an isolated environment (no global Python pollution)
- Installs dependencies automatically
- Runs the MCP server

---

## 🥈 Option 2 — Local installation (ZIP / Git clone)

### Step 1: Clone repository

```bash
git clone https://github.com/seth2k2/notebook_mcp.git
cd notebook_mcp
```
*Or download ZIP and extract it.*

### Step 2: Create virtual environment

```bash
python -m venv .venv
```

### Step 3: Activate environment

**Windows**
```bash
.venv\Scripts\activate
```

**Mac/Linux**
```bash
source .venv/bin/activate
```

### Step 4: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Run MCP server

```bash
python notebook_mcp.py
```

### 🔌 MCP Config (local setup)

**Windows Config:**
```json
{
  "mcpServers": {
    "notebook": {
      "command": ".venv/Scripts/python",
      "args": [
        "notebook_mcp.py"
      ]
    }
  }
}
```

**Mac/Linux Config:**
```json
{
  "mcpServers": {
    "notebook": {
      "command": ".venv/bin/python",
      "args": [
        "notebook_mcp.py"
      ]
    }
  }
}
```

