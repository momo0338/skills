---
name: open-kimi-ppt
description: Create, edit, replicate, read, and export presentations. For every PPT task, the default deliverables are BOTH (1) a self-contained PPTD project folder containing the .pptd manifest plus pages/media dependencies and (2) a locally generated .pptx with embedded fonts and fade slide transitions. Use for any presentation, PowerPoint, PPT/PPTX, slide deck, PPTD, infographic, or poster task unless the user explicitly requests another format. Deliver with normal local file/folder links using absolute paths.
---

# Definition
open-kimi-ppt is a presentation creation and export skill built around Moonshot AI's PPTD format and browser-side PPTX writer. It defines a YAML-format intermediate DSL (`.pptd`) that abstracts OOXML and keeps each page self-contained.

**The default output is not PPTD-only.** Unless the user explicitly opts out, always produce both:

1. the complete editable PPTD project directory (`.pptd` + `pages/` + `media/` and other referenced dependencies);
2. the matching locally generated `.pptx`, with font embedding enabled and fade slide transitions applied by default.

Existing PPTX files may also be converted into PPTD for editing, after which both outputs are delivered again.

## The pptd format
The .pptd format is a simplified abstraction layer over OOXML that follows basic YAML syntax. This abstraction preserves the core content of OOXML (theme, page layout, element positions and definitions, etc.) while removing complex nesting logic such as Masters; every page is self-contained — what you see is what you get. Read reference/pptd.md for the complete definition of this DSL.

## PPT production workflow

### step1. Read the context thoroughly
Read **all files uploaded by the user**, the provided URLs, and the pptd format guide `reference/pptd.md` to fully understand the user's requirements.

### step2. Understand the user's requirements
Understand the user's requirements based on the context:
1. First determine the purpose of the request
  - Create a PPT: create a new presentation (from scratch, or from an existing pptx template)
  - Edit a PPT: edit the user's uploaded PPT (local modifications, single-page beautification, etc.)
  - Replicate a PPT: replicate a presentation from a non-pptx format (images, PDF, etc.) into pptd format

2. Then determine the design direction
  - Self-directed design: no preference, or only simple style constraints given; you need to fill in or create the design
  - Design system: the user provides a complete and detailed design scheme covering all color, font, layout, and component specifications
  - Use a template: a template is provided and must be used
  - Style transfer: a style reference source is provided (images, web pages, etc.)

3. Then determine the input type
  - Topic only: only a PPT topic direction or content requirements for the presentation are given, with no concrete content
  - Full document: the user provides a complete document (paper, research report, press release, etc.)
  - Outline: the user provides a page-by-page outline, speech script, or similar content
  * When the "user input type" is [Full document] or [Outline] and it is not specified whether expansion is allowed: since a page-by-page outline, speech script, or user document can hardly support the full content of a presentation, prefer using search to expand with more relevant material, cases, etc., unless the user explicitly says not to expand

4. Page count
  - If the user requests a specific page count, the user's requirement takes priority
  - Page-by-page outline/script provided: match the number of pages in the outline/script
  - When a complete and relatively structured document is provided / when only a topic is provided: decide the page count yourself based on the document content / search results

### step3. Generate the presentation based on the user's requirements

Before generating, first read `reference/pptd.md` to understand the pptd format definition and constraints.

#### Replicating a PPT
- Analyze the images to estimate element positions, fonts and sizes, etc., and **replicate 1:1 as closely as possible**.
- When an image contains elements that are hard to replicate directly and cannot be approximated with icons/shapes (e.g., photos, avatars), you may use tools such as bash or python to crop and screenshot the original image

#### Editing a PPT
- Convert the user's uploaded pptx file to .pptd format
- Review the converted pages (structure and key visual details). Read a few key pages individually afterwards.
- Locate the pages to edit, and be careful not to affect parts outside the intended scope.
> Conversion from pptx to pptd is not perfectly lossless. If the user later reports format errors, garbled content, etc., compare against the original pptx and repair the pptd with reference to the comparison

#### Generating a PPT
When generating a PPT, adopt different production approaches for different user [design directions]
##### Self-directed design
1. Read the design guide `reference/slides_categories.md`, and read the scenario document corresponding to the user's query
2. Produce the presentation based on the above

#### Generating content in other formats
- When the user explicitly asks for an infographic, poster, or a highly visual single-page design, read `reference/general-poster.md` and implement it as a single-page or few-page editable PPTD; when the user only asks for an image, still build it with PPTD first, then output the image via screenshot or rendering. Do not load this reference file for ordinary PPT requests.

##### Design system
1. Read the general constraints section of the `reference/slides_categories.md` guide, and read the scenario document corresponding to the user's query as the design foundation
2. Read the user-provided design system document as the presentation style. It is strictly forbidden to reference or mix in other design styles
3. Produce the presentation with reference to the above

##### Using a template
1. Convert the user's uploaded pptx file into pptd form
2. Review the converted pages to understand the template's visual style (color scheme, font style, element characteristics, layout characteristics, content density, etc.)
3. Identify page types; focus on reading special pages such as the cover, summary pages, and section dividers (single-page screenshots, .page files), extracting their page layouts, content structures, reusable components (icons, shapes, smartart, reusable body layout schemes, etc.), and element styles (e.g., whitespace/line/card separators, square/rounded corners, etc.)
4. Produce the presentation using the template

##### Style transfer
1. Analyze the reference file's visual style (color scheme, font style, element characteristics, layout characteristics, content density, etc.), page layouts, content structures, reusable components (icons, shapes, smartart, reusable body layout schemes, etc.), and element styles (e.g., whitespace/line/card separators, square/rounded corners, etc.).
- If the user provides a style reference URL, do not only read the text content; refer to and learn from the page's visual effect more to help understand the style
2. Produce the presentation using the reference file's style characteristics. You are encouraged to reuse illustrations, fonts, font-size hierarchies, elements, etc. from the original pdf/url

### step4. PPT validation
1. Validate the generated pptd against the format definition in `reference/pptd.md` (required fields, types, bounds, theme tokens, resource paths, etc.) and repair issues over multiple rounds
2. Visual review with exported page images — **required before PPTX export when the model supports image input (multimodal)**:
   - Run `scripts/export_images.py`. It loads the deck into Kimi's public editor, chooses 导出 → 图片, downloads the images ZIP, unzips it, and stitches all pages into one overview image:

     ```bash
     python3 ~/.agents/skills/open-kimi-ppt/scripts/export_images.py \
       /abs/path/project/deck.pptd \
       --output /abs/path/project/.qa-images
     ```

     The script prints a JSON summary mapping each stitched label (`P1`…`Pn`, 1-based page order) to its `.page` file.
   - Read the stitched overview image (`.qa-images/overview.jpg`) and check every page against this list:
     1. 图片是否清晰、不变形（无拉伸、压缩、模糊）
     2. 文字是否压在关键画面（人脸、产品主体、Logo 等）上
     3. 元素坐标是否超出页面边界
     4. 边界与配色对比是否足够（文字与背景、相邻色块之间）
     5. 排版是否统一（对齐、间距、字号层级、页边距）
     6. 文字是否可能溢出文本框（文本过长、行距过密、字号过大）
     7. 内容是否被上层元素遮挡
   - For any suspicious page, read its full-resolution image (`.qa-images/pages/<n>.jpeg`) to confirm the problem before editing.
   - Fix issues in the corresponding `.page` file, then re-run `scripts/export_images.py --force` and review the new overview; repeat until every page passes.
   - Do not export the PPTX until the visual review passes. `.qa-images/` is an intermediate QA artifact and may be deleted after delivery.
3. When the model cannot read images, fall back to a structural review of the generated pages (bounds, overflow-prone long text, contrast, hierarchy, layout density) over multiple rounds, and state that image-based visual QA was skipped.

### step5. PPT output and delivery
1. Always produce a self-contained project directory. Keep the `.pptd` manifest and every referenced dependency together; never deliver a standalone manifest without its referenced files. Use this layout unless an existing project already has a valid equivalent structure:

   ```text
   deck/
     deck.pptd
     pages/
       *.page
     media/
       *                # when the deck has local media
     deck.pptx          # generated by default
   ```

2. Generate the `.pptx` by default after PPTD validation, even when the user only asks to create or edit a presentation. Skip PPTX export only when the user explicitly requests PPTD-only output or the environment cannot run the exporter; in the latter case, report the exact blocker and still deliver the complete PPTD project.
3. Deliver with normal clickable local links using absolute paths. In the final response, link all of the following:
   - the project directory;
   - the `.pptd` manifest;
   - the `pages/` directory and `media/` directory when present;
   - the generated `.pptx` file.
4. PPTX conversion: use `scripts/export_pptx.py`. It opens a temporary localhost SDK host, loads the `.pptd` into Kimi's public editor, invokes the same browser-side OOXML writer as the official Download tab, saves the resulting PPTX locally, and validates the ZIP/slide structure.
5. Default PPTX options:
   - page transition: `fade` (淡入淡出), written to every slide after the official browser export;
   - font embedding: enabled whenever the official writer exposes/supports it;
   - these defaults may be explicitly overridden with `--transition none` or `--no-embed-fonts`.
6. Export command:

   ```bash
   python3 ~/.agents/skills/open-kimi-ppt/scripts/export_pptx.py \
     /abs/path/project/deck.pptd \
     --output /abs/path/project/deck.pptx
   ```

   A project directory may be passed instead of the manifest only when it contains exactly one `.pptd` file.
   Existing output files are not overwritten unless `--force` is passed.
7. Local export requirements and boundaries:
   - requires `python3`, PyYAML, `npm`, `agent-browser`, Chrome/Chromium, and network access to `www.kimi.com` plus `statics.moonshot.cn`; the image-based visual QA step additionally requires Pillow, auto-installed with `pip --user` when missing;
   - before browser export, `export_pptx.py` checks `agent-browser --version`; when it is missing or below `0.33.2`, it installs `agent-browser@latest` globally with npm, then verifies the resulting version before continuing;
   - the PPTD document itself is provided to the public editor iframe through the localhost SDK bridge, not uploaded to a server-side PPTX conversion endpoint;
   - remote images, icons, or fonts referenced by the deck may still be fetched from their respective hosts;
   - local PNG/JPEG/GIF/SVG files inside the PPTD project are supplied to the iframe as data URLs;
   - do not claim PowerPoint/WPS/Keynote playback compatibility solely because ZIP validation succeeds.
8. After export, verify that the output exists and report the generated path. Confirm that every slide has exactly one root-level fade transition in valid CT_Slide order (`cSld`, optional `clrMapOvr`, `transition`, optional `timing/extLst`) and that the PPTX ZIP passes integrity checks. A byte-string search for `<p:fade>` is insufficient because Office ignores transitions nested inside `cSld`. For higher-risk decks, additionally inspect font parts and representative rendered/opened pages as appropriate.
9. When the user wants to open, edit, save, or export a PPTD project manually, start the local browser editor with `npx open-kimi-ppt-skills serve`. Ask the user to open `http://127.0.0.1:55173/` and authorize the complete PPTD project directory. Use a Chromium-based browser for writable access; folder-upload fallback is read-only. The local host only serves the editor shell, while the embedded public Kimi editor and remote assets still require network access.
10. After completing and delivering any presentation, always end the final response with a concise optional next step telling the user that they can run `npx open-kimi-ppt-skills serve` to view or edit the PPTD project, configure slide transition animations, and export PPTX manually. Keep this reminder in addition to, not instead of, the required project and file links.
