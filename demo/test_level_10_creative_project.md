# Project Proposal  
**Project Name:** **Koubou‑AI – A Conversational Design Assistant**  
**Repository:** `koubou-system`  
**Target File:** `test_level_10_creative_project.md`  

---

## 1. Executive Summary  

Koubou‑AI is a lightweight, cross‑platform desktop application that leverages GPT‑style language models to help designers, architects, and hobbyists generate rapid‑prototype sketches, mood boards, and design briefs. The app will be built on the existing `koubou-system` skeleton (Python 3, CLI‑first, modular architecture) and will extend it with a modern GUI, cloud‑based model inference, and a plugin ecosystem.  

The core value proposition: **“Design faster, iterate smarter, and collaborate seamlessly.”**  

---

## 2. Market Analysis  

| Segment | Size (2024) | Pain Points | Opportunity |
|---------|-------------|-------------|-------------|
| **Freelance Designers** | 1.2 M US, 3 M global | Time‑consuming ideation, lack of AI tools, high cost of design software | Low‑cost AI‑assisted ideation |
| **Architecture Firms** | 500 k US, 1.5 M global | Manual drafting, repetitive sketches, need for rapid concept validation | AI‑driven sketch generation, quick feedback loops |
| **Hobbyists & Makers** | 10 M US, 30 M global | Steep learning curve, expensive tools | Free or freemium AI‑assisted design workflow |
| **Education** | 2 M US, 5 M global | Limited access to design tools, need for interactive learning | Open‑source, teacher‑friendly AI modules |

**Competitive Landscape**

| Competitor | Strength | Weakness |
|------------|----------|----------|
| **Adobe Firefly** | Powerful AI, brand trust | Proprietary, high cost |
| **Canva Magic Write** | Easy UI, integrated | Limited to graphics, no sketching |
| **AutoCAD + ChatGPT** | Industry standard | No native AI integration |
| **OpenAI API + Custom UI** | Flexible | Requires custom development |

**Gap** – No single tool offers *AI‑driven sketch generation* with *real‑time collaboration* in a lightweight, open‑source package.

---

## 3. Technical Specification  

### 3.1 Architecture Overview  

```
┌───────────────────────┐
│  Frontend (PyQt5)     │
│  - Canvas, Toolbar,   │
│    Collaboration UI   │
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│  Core Engine (Python) │
│  - Model Wrapper       │
│  - Sketch Generator   │
│  - Plugin Manager     │
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│  Cloud Service Layer  │
│  - OpenAI / Cohere    │
│  - Auth, Rate‑limit   │
└───────────────────────┘
```

### 3.2 Core Modules  

| Module | Responsibility | Key Functions |
|--------|----------------|---------------|
| `koubou_system/cli.py` | CLI entry point (extends hello_world) | `run_cli()` |
| `koubou_system/gui.py` | PyQt5 GUI | `MainWindow`, `CanvasWidget` |
| `koubou_system/model.py` | API wrapper | `generate_sketch(prompt)`, `chat(prompt)` |
| `koubou_system/plugin.py` | Plugin interface | `load_plugins()`, `PluginBase` |
| `koubou_system/utils.py` | Helpers | `save_image()`, `load_image()` |

### 3.3 AI Integration  

* **Prompt Engineering** – Use a templated prompt that includes sketch style, dimensions, and user context.  
* **Model Choice** – Default to OpenAI’s `gpt-4o-mini` for text, and `dall-e-3` for image generation.  
* **Local Fallback** – Optionally use a fine‑tuned Stable Diffusion model for offline mode.  

### 3.4 Data Flow  

1. User enters prompt → `generate_sketch()`  
2. API returns base64 image → `CanvasWidget` renders  
3. User edits → `CanvasWidget` captures strokes → `save_image()`  

### 3.5 Dependencies  

| Package | Version | Purpose |
|---------|---------|---------|
| `PyQt5` | ≥5.15 | GUI |
| `requests` | ≥2.31 | HTTP client |
| `openai` | ≥1.0 | API SDK |
| `Pillow` | ≥10.0 | Image handling |
| `pluggy` | ≥1.5 | Plugin system |
| `pytest` | ≥8.0 | Testing |

### 3.6 Security & Privacy  

* All user data stored locally unless explicitly shared.  
* API keys stored in environment variables (`OPENAI_API_KEY`).  
* GDPR‑compliant data handling (no user data sent to third parties without consent).

---

## 4. UI/UX Design  

### 4.1 User Personas  

| Persona | Goals | Pain Points |
|---------|-------|-------------|
| **Mika, Freelance UI/UX Designer** | Rapidly prototype UI concepts | Time‑consuming sketching, need for quick feedback |
| **Ken, Architecture Student** | Generate building sketches | Limited CAD knowledge, expensive software |
| **Sakura, Hobbyist Maker** | Experiment with design ideas | No design background, steep learning curve |

### 4.2 Wireframes  

1. **Home Screen** – Prompt bar, “Generate” button, recent sketches gallery.  
2. **Canvas Screen** – Full‑screen canvas, toolbar (pen, eraser, color picker), “Export” button.  
3. **Collaboration Panel** – Real‑time chat, shared sketch view, version history.  

### 4.3 Interaction Flow  

1. **Prompt** → `Generate` → AI sketch appears.  
2. **Edit** → User draws on canvas.  
3. **Export** → PNG/JPEG/Sketch file.  
4. **Share** → Generate shareable link (cloud sync).  

### 4.4 Accessibility  

* Keyboard shortcuts for all actions.  
* High‑contrast theme.  
* Screen‑reader friendly labels.

---

## 5. Business Model  

| Model | Description | Revenue Streams |
|-------|-------------|-----------------|
| **Freemium** | Free core app with basic AI usage (limited prompts per month). | In‑app purchases: extra prompts, premium models, cloud storage. |
| **Enterprise** | Custom deployment for firms (on‑prem, dedicated API keys). | Subscription (annual), support contracts. |
| **Marketplace** | Plugin ecosystem where developers sell plugins (e.g., advanced CAD export). | 30% commission on plugin sales. |
| **Education** | Free tier for schools, discounted licenses for teachers. | Grants, sponsorships. |

---

## 6. Development Roadmap  

| Phase | Duration | Milestones | Deliverables |
|-------|----------|------------|--------------|
| **0.0 – Foundations** | 2 weeks | • Set up repo structure<br>• Implement CLI skeleton (extend `hello_world.py`) | `cli.py`, `__init__.py` |
| **0.1 – Core Engine** | 4 weeks | • `model.py` wrapper<br>• `utils.py` image helpers | `model.py`, `utils.py` |
| **1.0 – GUI Prototype** | 6 weeks | • PyQt5 canvas<br>• Prompt bar<br>• Basic rendering | `gui.py`, `main_window.ui` |
| **2.0 – AI Integration** | 4 weeks | • Prompt templates<br>• API calls<br>• Error handling | `model.py` updates |
| **3.0 – Collaboration** | 5 weeks | • Real‑time chat<br>• Shared sketch sync | `collab.py` |
| **4.0 – Plugin System** | 3 weeks | • `pluggy` integration<br>• Sample plugin | `plugin.py`, `sample_plugin/` |
| **5.0 – Testing & CI** | 3 weeks | • Unit tests<br>• GitHub Actions | `tests/` |
| **6.0 – Release & Marketing** | 2 weeks | • Packaging (pip, AppImage)<br>• Documentation | `setup.py`, `docs/` |
| **Ongoing** | Continuous | • Feature backlog<br>• Community support | GitHub Issues, Discord |

### Key Deliverable Dates  

| Date | Deliverable |
|------|-------------|
| **2025‑10‑01** | v0.1 CLI & core engine |
| **2025‑11‑15** | v1.0 GUI prototype |
| **2025‑12‑31** | v2.0 AI integration |
| **2026‑02‑28** | v3.0 Collaboration |
| **2026‑04‑30** | v4.0 Plugin system |
| **2026‑06‑15** | v5.0 Testing & CI |
| **2026‑07‑01** | v6.0 Release |

---

## 7. Risks & Mitigations  

| Risk | Impact | Mitigation |
|------|--------|------------|
| **API cost spikes** | High operational cost | Rate‑limit, local fallback, user quotas |
| **Model latency** | Poor UX | Caching, async UI updates |
| **Security breach** | Data loss | Encryption, secure key storage |
| **Low adoption** | Revenue shortfall | Community outreach, open‑source contributions |

---

## 8. Conclusion  

Koubou‑AI transforms the way designers and makers create visual concepts by combining a lightweight Python foundation with powerful AI models and a user‑friendly interface. By leveraging the existing `koubou-system` skeleton, we can deliver a rapid, maintainable product that fills a clear market gap and opens multiple revenue streams.  

--- 

*Prepared by:* **[Your Name]**  
*Date:* **2025‑08‑31**