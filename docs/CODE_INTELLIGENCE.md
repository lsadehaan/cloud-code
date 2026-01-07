# Code Intelligence - Future Phase

> **Status:** FUTURE PHASE - Not for initial implementation
>
> **Initial Approach:** Use vanilla claude-code for coding tasks. It has built-in file operations, grep, and basic code navigation that are sufficient for Phase 1-3.
>
> This document explores options for enhancing code intelligence capabilities in later phases.

---

## Table of Contents

1. [Overview](#overview)
2. [Current State](#current-state)
3. [Vector RAG for Code](#vector-rag-for-code)
4. [Language Server Protocol (LSP)](#language-server-protocol-lsp)
5. [Tree-sitter Parsing](#tree-sitter-parsing)
6. [Code Refactoring Tools](#code-refactoring-tools)
7. [Existing Solutions](#existing-solutions)
8. [Recommendation](#recommendation)

---

## Overview

Code intelligence refers to capabilities that help AI agents understand, navigate, and modify codebases more effectively:

- **Navigation**: "Where is this function defined?" "What calls this method?"
- **Understanding**: "What does this module do?" "How does data flow here?"
- **Refactoring**: "Rename this variable everywhere" "Extract this to a function"
- **Context Retrieval**: "Find code relevant to authentication"

---

## Current State

### What claude-code provides out of the box:
- File read/write operations
- Grep/ripgrep for text search
- Glob for file discovery
- Basic code understanding via LLM

### Limitations:
- Text search is imprecise (matches strings, not semantics)
- No understanding of code structure (AST)
- Can't find "usages of this variable" accurately
- Large codebases require many grep calls
- No refactoring tooling

---

## Vector RAG for Code

### Concept
Embed code chunks into vectors, store in vector database, retrieve semantically similar code for context.

### Common Approaches

**1. Naive chunking (by lines/tokens)**
```python
# Split file into chunks of N lines
chunks = split_file_by_lines(content, chunk_size=50)
embeddings = embed(chunks)
```
- Simple but breaks semantic units (functions, classes)

**2. AST-aware chunking**
```python
# Parse file, extract semantic units
tree = parse_to_ast(content, language="python")
chunks = extract_functions_and_classes(tree)
embeddings = embed(chunks)
```
- Preserves semantic boundaries
- Better retrieval quality

**3. Hybrid (text + structure)**
- Combine code text with structural metadata
- Include function signatures, docstrings, imports

### Vector Databases
| Database | Pros | Cons |
|----------|------|------|
| Chroma | Simple, embedded | Limited scale |
| Qdrant | Fast, filtering | More setup |
| Pinecone | Managed, scalable | Cost at scale |
| pgvector | PostgreSQL native | Slower |

### Embedding Models
| Model | Dimensions | Best For |
|-------|------------|----------|
| OpenAI text-embedding-3-small | 1536 | General purpose |
| Voyage code-2 | 1536 | Code-specific |
| CodeBERT | 768 | Open source |
| StarCoder embeddings | 1024 | Open source, code |

### Limitations of Vector RAG for Code

**Semantic search is bad at:**
- "Find all usages of `user_id` variable" (needs exact matching)
- "What inherits from `BaseModel`?" (needs type system)
- "What functions call `authenticate()`?" (needs call graph)

**Vector search finds:**
- Code that "talks about" similar concepts
- Implementations that "look like" the query
- NOT precise structural relationships

---

## Language Server Protocol (LSP)

### Concept
Use the same protocol that IDEs use for "Go to Definition", "Find References", etc.

### How it works
```
Agent → LSP Client → LSP Server (e.g., pyright) → Response
         └─ JSON-RPC over stdio ─┘
```

### Key Capabilities
| Feature | LSP Method | Example |
|---------|------------|---------|
| Go to Definition | `textDocument/definition` | Jump to function source |
| Find References | `textDocument/references` | All usages of a symbol |
| Hover | `textDocument/hover` | Type info, docstring |
| Rename | `textDocument/rename` | Safe renaming across files |
| Code Actions | `textDocument/codeAction` | Quick fixes, refactors |
| Diagnostics | `textDocument/publishDiagnostics` | Errors, warnings |

### Language Servers by Language
| Language | Server | Notes |
|----------|--------|-------|
| Python | pyright, pylsp | pyright is faster |
| TypeScript/JS | typescript-language-server | Official |
| Go | gopls | Official |
| Rust | rust-analyzer | Excellent |
| Java | Eclipse JDT LS | Full featured |
| C/C++ | clangd | LLVM-based |

### Integration Approach

```python
class LSPTool:
    """MCP tool that wraps LSP operations."""

    def __init__(self, workspace_path: Path):
        self.servers = {}  # language -> LSP server process

    async def start_server(self, language: str):
        """Start LSP server for language."""
        if language == "python":
            proc = await asyncio.create_subprocess_exec(
                "pyright-langserver", "--stdio",
                stdin=PIPE, stdout=PIPE
            )
            self.servers["python"] = LSPClient(proc)

    async def find_references(self, file: Path, line: int, col: int) -> list[Location]:
        """Find all references to symbol at position."""
        server = self._get_server_for_file(file)
        return await server.request("textDocument/references", {
            "textDocument": {"uri": file.as_uri()},
            "position": {"line": line, "character": col},
            "context": {"includeDeclaration": True}
        })

    async def go_to_definition(self, file: Path, line: int, col: int) -> Location:
        """Jump to definition of symbol."""
        server = self._get_server_for_file(file)
        return await server.request("textDocument/definition", {
            "textDocument": {"uri": file.as_uri()},
            "position": {"line": line, "character": col}
        })

    async def rename_symbol(self, file: Path, line: int, col: int, new_name: str) -> WorkspaceEdit:
        """Rename symbol across entire workspace."""
        server = self._get_server_for_file(file)
        return await server.request("textDocument/rename", {
            "textDocument": {"uri": file.as_uri()},
            "position": {"line": line, "character": col},
            "newName": new_name
        })
```

### Advantages over Vector RAG
- **Precise**: Exact references, not fuzzy matches
- **Complete**: Finds ALL usages, not top-k similar
- **Type-aware**: Understands inheritance, generics, etc.
- **Refactoring**: Safe renames, extract function, etc.

### Limitations
- Requires language-specific servers
- Setup complexity per language
- Memory usage (LSP servers hold full project state)
- Not semantic (can't "find authentication code")

---

## Tree-sitter Parsing

### Concept
Fast, incremental parser that builds concrete syntax trees for many languages.

### Use Cases
- AST-aware code chunking for RAG
- Code navigation without full LSP
- Syntax highlighting
- Code transformation

### Example: Extract Functions

```python
import tree_sitter_python as ts_python
from tree_sitter import Language, Parser

PY_LANGUAGE = Language(ts_python.language())
parser = Parser(PY_LANGUAGE)

def extract_functions(code: str) -> list[dict]:
    """Extract all function definitions from Python code."""
    tree = parser.parse(code.encode())
    functions = []

    def visit(node):
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            functions.append({
                "name": name_node.text.decode(),
                "start_line": node.start_point[0],
                "end_line": node.end_point[0],
                "code": code[node.start_byte:node.end_byte]
            })
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return functions
```

### When to Use Tree-sitter
- Building AST-aware RAG indexes
- Code analysis without full language server
- Fast structural queries
- Multi-language support (one parser, many grammars)

---

## Code Refactoring Tools

### Rope (Python)
```python
from rope.base.project import Project
from rope.refactor.rename import Rename

project = Project('/path/to/project')
resource = project.get_resource('module.py')

# Rename a function
renamer = Rename(project, resource, offset=123)  # offset of 'old_name'
changes = renamer.get_changes('new_name')
project.do(changes)
```

### jscodeshift (JavaScript/TypeScript)
```javascript
// Transform: rename all `foo` to `bar`
module.exports = function(fileInfo, api) {
  return api.jscodeshift(fileInfo.source)
    .findVariableDeclarators('foo')
    .renameTo('bar')
    .toSource();
};
```

### LibCST (Python)
```python
import libcst as cst

class RenameTransformer(cst.CSTTransformer):
    def leave_Name(self, original, updated):
        if updated.value == "old_name":
            return updated.with_changes(value="new_name")
        return updated

# Apply transformation
tree = cst.parse_module(source_code)
new_tree = tree.visit(RenameTransformer())
print(new_tree.code)
```

---

## Existing Solutions

### 1. Aider
- Uses tree-sitter for repo mapping
- Creates "repo map" showing file structure + key symbols
- Selective context retrieval based on relevance
- https://aider.chat/

### 2. Continue.dev
- VS Code extension with RAG-based context
- Uses embeddings + reranking
- Integrates with LSP for navigation
- https://continue.dev/

### 3. Cursor
- Proprietary codebase indexing
- "@ mentions" for context injection
- Unclear internals
- https://cursor.sh/

### 4. Cody (Sourcegraph)
- Enterprise code search
- Graph-based code intelligence
- Cross-repo context
- https://sourcegraph.com/cody

### 5. Sweep AI
- GitHub issue → PR automation
- Uses vector search + call graph analysis
- Open source
- https://github.com/sweepai/sweep

### 6. Codegen (from Codegen.com)
- Code analysis and generation platform
- Multi-language support
- Focus on enterprise workflows
- https://codegen.com/

### 7. MCP Servers (for claude-code)
| Server | Capabilities |
|--------|--------------|
| `@anthropics/mcp-server-github` | GitHub API access |
| `@anthropics/mcp-server-filesystem` | File operations |
| Community LSP servers | Language server integration |

---

## Recommendation

### Phase 1-3: Vanilla claude-code
- Built-in file operations sufficient
- grep/glob for navigation
- LLM understands code from context
- Focus on core workflow, not optimization

### Phase 4+: Evaluate Adding

**Priority 1: LSP Integration (Highest ROI)**
- Start with Python (pyright) and TypeScript (tsserver)
- Wrap as MCP tool: `lsp_find_references`, `lsp_go_to_definition`, `lsp_rename`
- Dramatically improves precision for "find usages" type queries

**Priority 2: AST-aware RAG**
- Use tree-sitter for chunking (not naive line splits)
- Index at function/class granularity
- Combine with LSP for best of both worlds

**Priority 3: Language-specific refactoring**
- Rope for Python refactoring
- jscodeshift for JS/TS
- Only if agents frequently need safe refactoring

### Integration Architecture (Future)

```
┌─────────────────────────────────────────────────────┐
│                    Agent Container                    │
│                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ claude-code │  │  LSP Tool   │  │  RAG Tool   │  │
│  │  (primary)  │  │  (precise)  │  │ (semantic)  │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │
│         │                │                │         │
│         └────────────────┼────────────────┘         │
│                          │                          │
│                    MCP Protocol                     │
└─────────────────────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ┌────────┐  ┌────────┐  ┌────────┐
         │pyright │  │tsserver│  │ gopls  │
         └────────┘  └────────┘  └────────┘
              LSP Servers (per language)
```

---

## Open Questions

1. **Should RAG index be project-specific or shared?**
   - Project-specific: More accurate, more storage
   - Shared embeddings: Reuse across similar projects

2. **LSP server lifecycle management?**
   - Start on demand vs. keep warm
   - Memory vs. latency tradeoff

3. **How to handle polyglot repos?**
   - Multiple LSP servers
   - Which takes precedence?

4. **Incremental indexing?**
   - Re-index on every commit?
   - Watch for file changes?

---

## References

- [LSP Specification](https://microsoft.github.io/language-server-protocol/)
- [Tree-sitter](https://tree-sitter.github.io/tree-sitter/)
- [Aider Repo Map](https://aider.chat/docs/repomap.html)
- [Voyage AI Code Embeddings](https://docs.voyageai.com/docs/embeddings)
- [pyright](https://github.com/microsoft/pyright)

---

*Document created: January 2026*
*Last updated: January 2026*
*Status: Future Phase - For Reference Only*
