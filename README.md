<p align="center">
  <a href="docs/BANNER.md">
    <img src="./assets/life-banner.gif" width="100%"
         alt="Conway's Game of Life: a glider gun in a server rack streams gliders into a 3D printer, which prints a honey farm on its bed while a quadcopter hovers above and a telescope watches Orion">
  </a>
</p>

# Harshavardhan M

**I build systems that eventually make things.**

Distributed systems and infrastructure on one side of the desk; 3D printers, FPV quads and a telescope on the other.
Bengaluru, India · founder of [OneCreations](https://onecreations.in)

<sub>The banner above is not an animation <i>of</i> the Game of Life. Every frame is one exact generation of Conway's rules: the gun in the rack streams gliders to the printer, and five gliders print a honey farm on the bed and take it apart again. <a href="docs/BANNER.md">How it's built and verified →</a></sub>

---

### OneCreations

[**onecreations.in**](https://onecreations.in) is my workshop: a place for objects, films and experiments, made out of curiosity.
It is where the software turns into something you can hold: 3D-printed parts and custom models, fabrication and CNC, electronics and drones, astrophotography, animation and VFX.

### What I work on

| | | in the banner |
|---|---|---|
| **Systems** | Backend services, distributed systems, cloud and infrastructure. Software that has to stay correct under load, failure and concurrency, and software that talks to physical machines. | the rack and its glider gun |
| **Making** | 3D printing, custom models and fabrication, print-farm experiments, and the manufacturing side of turning designs into parts. | the printer and the part on its bed |
| **Flight** | FPV quadcopters: building, tuning and flying them, and the electronics in between. | the quad with blinker props |
| **Sky** | Astrophotography: the night sky through a telescope, one long exposure at a time. | Orion, with M42 as a pulsar |

### Selected work

| | |
|---|---|
| [**Docksmith**](https://github.com/harsha135135/Docksmith) | A Docker-like build and runtime system from scratch: content-addressed layers, a deterministic build cache, and container isolation with Linux namespaces and `pivot_root`. No Docker, runc or containerd. |
| [**sentinel**](https://github.com/harsha135135/sentinel) | A self-healing code agent that runs model-written code in a locked-down Docker sandbox. Every mitigation has a test that performs the attack (33/33 contained), and the repair loop is provably terminating. |
| [**agent-systems**](https://github.com/harsha135135/agent-systems) | An MCP server written by hand over raw JSON-RPC 2.0 stdio, with wire-level conformance tests, exposing a real retrieval service. |
| [**retrieval-lab**](https://github.com/harsha135135/retrieval-lab) | Hybrid retrieval (hard metadata filters plus vectors) with a deterministic citation validator and a retriever-agnostic evaluation harness. |
| [**intelligent-water-management-system**](https://github.com/harsha135135/intelligent-water-management-system) | Team capstone: hourly water-demand forecasting for 24 campus tanks with Chronos-2 zero-shot, significantly beating the deployed incumbent at every horizon. |

<!--
  Placeholders: add these when they are public, or remove.
  | [**life-lab**](https://github.com/harsha135135/life-lab) | HashLife in Rust/WASM, a WebGL viewer, a physically executed OTCA metapixel, and verifiable pattern-repair experiments. |
  | [**adscale**](https://github.com/harsha135135/adscale) | Advertising backend: atomic budget enforcement, idempotency, Redis caching, transactional outbox + Kafka. |
  | [**One3D**](https://github.com/harsha135135/One3D) | (describe) |
  | Making / Flight / Sky: link builds, prints, flight footage or astro images here, e.g. on onecreations.in. |
-->

<sub>Banner: my own Life engine in Python, no Life libraries. <code>python -m life.generate</code> renders it; <code>python -m life.verify</code> decodes the GIF back into cells and checks every one of its 7.8 million cell updates against B3/S23.</sub>
