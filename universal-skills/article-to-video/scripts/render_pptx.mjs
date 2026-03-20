import fs from "fs";
import path from "path";
import { createRequire } from "module";

const require = createRequire(import.meta.url);
const PptxGenJS = require("pptxgenjs");

const slideSpecPath = process.argv[2];
const outputPath = process.argv[3];

if (!slideSpecPath || !outputPath) {
  console.error("Usage: node render_pptx.mjs <slide-spec.json> <output.pptx>");
  process.exit(1);
}

const spec = JSON.parse(fs.readFileSync(slideSpecPath, "utf8"));
const render = spec.render || {};
const theme = spec.theme || {};
const palette = theme.palette || {};
const fonts = theme.font || {};

const SLIDE_W = 13.333333;
const SLIDE_H = 7.5;
const pxWidth = Number(render.width || 1920);
const pxHeight = Number(render.height || 1080);
const xIn = (value) => (Number(value || 0) / pxWidth) * SLIDE_W;
const yIn = (value) => (Number(value || 0) / pxHeight) * SLIDE_H;

const pptx = new PptxGenJS();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "Codex article-to-video";
pptx.company = "oh-my-skills";
pptx.subject = "Article to video deck";
pptx.title = spec.title || path.basename(outputPath, path.extname(outputPath));
pptx.lang = "zh-CN";

function color(hex, fallback = "000000") {
  const raw = String(hex || fallback).replace(/^#/, "").trim();
  return raw || fallback;
}

function addText(slide, text, opts) {
  slide.addText(text || "", {
    margin: 0,
    fit: "shrink",
    breakLine: false,
    ...opts,
  });
}

function addPanel(slide, x, y, w, h, fillColor, lineColor, lineWidth = 1) {
  slide.addShape(pptx.ShapeType.rect, {
    x,
    y,
    w,
    h,
    fill: { color: color(fillColor, "FFFFFF") },
    line: { color: color(lineColor, "FFFFFF"), width: lineWidth },
  });
}

function addAccentBar(slide, x, y, w, h, accent) {
  slide.addShape(pptx.ShapeType.rect, {
    x,
    y,
    w,
    h,
    line: { color: color(accent, "8F2D1F"), width: 0 },
    fill: { color: color(accent, "8F2D1F") },
  });
}

function renderFrame(slide) {
  slide.addShape(pptx.ShapeType.rect, {
    x: xIn(28),
    y: yIn(28),
    w: xIn(pxWidth - 56),
    h: yIn(pxHeight - 56),
    fill: { transparency: 100 },
    line: { color: color(palette.line, "D8C9B8"), width: 1 },
  });
}

function renderFooter(slide, page) {
  const footer = page.footer || {};
  const safeHeight = Number(footer.safe_height || render.footer_safe_height || 156);
  const top = pxHeight - safeHeight;

  addPanel(
    slide,
    0,
    yIn(top),
    SLIDE_W,
    yIn(safeHeight),
    palette.paperStrong || "EFE3D4",
    palette.paperStrong || "EFE3D4",
    0
  );

  slide.addShape(pptx.ShapeType.line, {
    x: xIn(70),
    y: yIn(top),
    w: xIn(pxWidth - 140),
    h: 0,
    line: { color: color(palette.line, "D8C9B8"), width: 1 },
  });

  addText(slide, footer.left || "", {
    x: xIn(96),
    y: yIn(top + 34),
    w: xIn(900),
    h: yIn(40),
    fontFace: fonts.label || "Bahnschrift",
    fontSize: 11,
    color: color(palette.muted, "5C544D"),
  });

  addText(slide, footer.right || "", {
    x: xIn(pxWidth - 160),
    y: yIn(top + 34),
    w: xIn(64),
    h: yIn(40),
    align: "right",
    fontFace: fonts.label || "Bahnschrift",
    fontSize: 11,
    color: color(palette.muted, "5C544D"),
  });
}

function renderEyebrow(slide, page) {
  addText(slide, page.eyebrow || "", {
    x: xIn(72),
    y: yIn(70),
    w: xIn(320),
    h: yIn(24),
    fontFace: fonts.label || "Bahnschrift",
    fontSize: 12,
    bold: true,
    color: color(palette.accent, "8F2D1F"),
  });
}

function renderCover(slide, page) {
  renderEyebrow(slide, page);

  addText(slide, page.heading || "", {
    x: xIn(72),
    y: yIn(126),
    w: xIn(760),
    h: yIn(180),
    fontFace: fonts.heading || "Microsoft YaHei UI",
    fontSize: 30,
    bold: true,
    color: color(palette.ink, "181512"),
  });

  addText(slide, page.summary || "", {
    x: xIn(72),
    y: yIn(302),
    w: xIn(560),
    h: yIn(96),
    fontFace: fonts.body || "Microsoft YaHei UI",
    fontSize: 15,
    color: color(palette.muted, "5C544D"),
  });

  addPanel(
    slide,
    xIn(1040),
    yIn(168),
    xIn(728),
    yIn(260),
    palette.paperStrong || "EDE2D4",
    palette.line || "D8C9B8"
  );
  addAccentBar(slide, xIn(1040), yIn(168), xIn(728), yIn(4), palette.accent || "8F2D1F");

  addText(slide, page.summary || "", {
    x: xIn(1084),
    y: yIn(236),
    w: xIn(640),
    h: yIn(132),
    fontFace: fonts.body || "Microsoft YaHei UI",
    fontSize: 16,
    color: color(palette.ink, "181512"),
  });

  const highlights = Array.isArray(page.highlights) ? page.highlights.slice(0, 3) : [];
  highlights.forEach((item, index) => {
    const left = 1040 + index * 244;
    addPanel(
      slide,
      xIn(left),
      yIn(470),
      xIn(220),
      yIn(140),
      "FBF7F1",
      palette.line || "D8C9B8"
    );
    addAccentBar(slide, xIn(left), yIn(470), xIn(220), yIn(4), palette.accent || "8F2D1F");
    addText(slide, String(index + 1), {
      x: xIn(left + 14),
      y: yIn(488),
      w: xIn(32),
      h: yIn(28),
      fontFace: fonts.label || "Bahnschrift",
      fontSize: 20,
      bold: true,
      color: color(palette.ink, "181512"),
    });
    addText(slide, item, {
      x: xIn(left + 14),
      y: yIn(530),
      w: xIn(190),
      h: yIn(62),
      fontFace: fonts.body || "Microsoft YaHei UI",
      fontSize: 11,
      color: color(palette.muted, "5C544D"),
    });
  });
}

function renderHeadlineBullets(slide, page) {
  renderEyebrow(slide, page);

  addText(slide, page.heading || "", {
    x: xIn(72),
    y: yIn(126),
    w: xIn(980),
    h: yIn(86),
    fontFace: fonts.heading || "Microsoft YaHei UI",
    fontSize: 28,
    bold: true,
    color: color(palette.ink, "181512"),
  });

  addText(slide, page.summary || "", {
    x: xIn(72),
    y: yIn(206),
    w: xIn(1040),
    h: yIn(58),
    fontFace: fonts.body || "Microsoft YaHei UI",
    fontSize: 14,
    color: color(palette.muted, "5C544D"),
  });

  const bullets = Array.isArray(page.bullets) ? page.bullets.slice(0, 5) : [];
  let top = 292;
  bullets.forEach((bullet) => {
    slide.addShape(pptx.ShapeType.ellipse, {
      x: xIn(88),
      y: yIn(top + 10),
      w: xIn(10),
      h: yIn(10),
      line: { color: color(palette.accent, "8F2D1F"), width: 0 },
      fill: { color: color(palette.accent, "8F2D1F") },
    });
    addText(slide, bullet, {
      x: xIn(112),
      y: yIn(top),
      w: xIn(1040),
      h: yIn(38),
      fontFace: fonts.body || "Microsoft YaHei UI",
      fontSize: 18,
      color: color(palette.ink, "181512"),
    });
    top += 46;
  });
}

function renderCardGrid(slide, page, columns) {
  renderEyebrow(slide, page);

  addText(slide, page.heading || "", {
    x: xIn(72),
    y: yIn(126),
    w: xIn(1120),
    h: yIn(80),
    fontFace: fonts.heading || "Microsoft YaHei UI",
    fontSize: 28,
    bold: true,
    color: color(palette.ink, "181512"),
  });

  addText(slide, page.summary || "", {
    x: xIn(72),
    y: yIn(206),
    w: xIn(1120),
    h: yIn(54),
    fontFace: fonts.body || "Microsoft YaHei UI",
    fontSize: 14,
    color: color(palette.muted, "5C544D"),
  });

  const cards = Array.isArray(page.cards) ? page.cards : [];
  const gap = 18;
  const totalWidth = 1776;
  const cardWidth = Math.floor((totalWidth - gap * (columns - 1)) / columns);
  const baseTop = 286;

  cards.forEach((card, index) => {
    const row = Math.floor(index / columns);
    const col = index % columns;
    const left = 72 + col * (cardWidth + gap);
    const top = baseTop + row * 176;
    addPanel(
      slide,
      xIn(left),
      yIn(top),
      xIn(cardWidth),
      yIn(148),
      "FBF7F1",
      palette.line || "D8C9B8"
    );
    addAccentBar(slide, xIn(left), yIn(top), xIn(cardWidth), yIn(4), palette.accent || "8F2D1F");
    addText(slide, card.title || "", {
      x: xIn(left + 14),
      y: yIn(top + 18),
      w: xIn(cardWidth - 28),
      h: yIn(28),
      fontFace: fonts.heading || "Microsoft YaHei UI",
      fontSize: 15,
      bold: true,
      color: color(palette.ink, "181512"),
    });
    addText(slide, card.body || "", {
      x: xIn(left + 14),
      y: yIn(top + 54),
      w: xIn(cardWidth - 28),
      h: yIn(70),
      fontFace: fonts.body || "Microsoft YaHei UI",
      fontSize: 10.5,
      color: color(palette.muted, "5C544D"),
    });
  });
}

function renderPillars(slide, page) {
  renderEyebrow(slide, page);

  addText(slide, page.heading || "", {
    x: xIn(72),
    y: yIn(126),
    w: xIn(1120),
    h: yIn(82),
    fontFace: fonts.heading || "Microsoft YaHei UI",
    fontSize: 28,
    bold: true,
    color: color(palette.ink, "181512"),
  });

  addText(slide, page.summary || "", {
    x: xIn(72),
    y: yIn(208),
    w: xIn(1160),
    h: yIn(52),
    fontFace: fonts.body || "Microsoft YaHei UI",
    fontSize: 14,
    color: color(palette.muted, "5C544D"),
  });

  const cards = Array.isArray(page.cards) ? page.cards.slice(0, 3) : [];
  cards.forEach((card, index) => {
    const left = 72 + index * 600;
    const top = 300;
    addPanel(
      slide,
      xIn(left),
      yIn(top),
      xIn(552),
      yIn(250),
      "FBF7F1",
      palette.line || "D8C9B8"
    );
    addAccentBar(slide, xIn(left), yIn(top), xIn(552), yIn(6), palette.accent || "8F2D1F");

    slide.addShape(pptx.ShapeType.ellipse, {
      x: xIn(left + 18),
      y: yIn(top + 22),
      w: xIn(52),
      h: yIn(52),
      line: { color: color(palette.paperStrong, "EBE1D3"), width: 0 },
      fill: { color: color(palette.paperStrong, "EBE1D3") },
    });
    addText(slide, String(index + 1), {
      x: xIn(left + 32),
      y: yIn(top + 32),
      w: xIn(24),
      h: yIn(22),
      align: "center",
      fontFace: fonts.label || "Bahnschrift",
      fontSize: 14,
      bold: true,
      color: color(palette.accent, "8F2D1F"),
    });

    addText(slide, card.title || "", {
      x: xIn(left + 86),
      y: yIn(top + 28),
      w: xIn(430),
      h: yIn(34),
      fontFace: fonts.heading || "Microsoft YaHei UI",
      fontSize: 16,
      bold: true,
      color: color(palette.ink, "181512"),
    });

    addText(slide, card.body || "", {
      x: xIn(left + 24),
      y: yIn(top + 98),
      w: xIn(500),
      h: yIn(104),
      fontFace: fonts.body || "Microsoft YaHei UI",
      fontSize: 12,
      color: color(palette.muted, "5C544D"),
    });
  });
}

function renderComparison(slide, page) {
  renderEyebrow(slide, page);

  addText(slide, page.heading || "", {
    x: xIn(72),
    y: yIn(126),
    w: xIn(1120),
    h: yIn(80),
    fontFace: fonts.heading || "Microsoft YaHei UI",
    fontSize: 28,
    bold: true,
    color: color(palette.ink, "181512"),
  });

  addText(slide, page.summary || "", {
    x: xIn(72),
    y: yIn(206),
    w: xIn(1120),
    h: yIn(54),
    fontFace: fonts.body || "Microsoft YaHei UI",
    fontSize: 14,
    color: color(palette.muted, "5C544D"),
  });

  const leftBlock = page.left || (Array.isArray(page.cards) ? page.cards[0] : null) || {};
  const rightBlock = page.right || (Array.isArray(page.cards) ? page.cards[1] : null) || {};
  const blocks = [leftBlock, rightBlock];
  blocks.forEach((block, index) => {
    const left = 72 + index * 900;
    addPanel(
      slide,
      xIn(left),
      yIn(290),
      xIn(858),
      yIn(240),
      "FBF7F1",
      palette.line || "D8C9B8"
    );
    addAccentBar(slide, xIn(left), yIn(290), xIn(858), yIn(4), index === 0 ? (palette.accent || "8F2D1F") : (palette.ink || "181512"));
    addText(slide, block.title || "", {
      x: xIn(left + 16),
      y: yIn(310),
      w: xIn(820),
      h: yIn(30),
      fontFace: fonts.heading || "Microsoft YaHei UI",
      fontSize: 16,
      bold: true,
      color: color(palette.ink, "181512"),
    });
    const bodyLines = []
      .concat(block.body ? [block.body] : [])
      .concat(Array.isArray(block.bullets) ? block.bullets : []);
    addText(slide, bodyLines.join("\n"), {
      x: xIn(left + 16),
      y: yIn(354),
      w: xIn(820),
      h: yIn(140),
      breakLine: true,
      fontFace: fonts.body || "Microsoft YaHei UI",
      fontSize: 11.5,
      color: color(palette.muted, "5C544D"),
    });
  });
}

function renderProcessFlow(slide, page) {
  renderEyebrow(slide, page);

  addText(slide, page.heading || "", {
    x: xIn(72),
    y: yIn(126),
    w: xIn(1140),
    h: yIn(82),
    fontFace: fonts.heading || "Microsoft YaHei UI",
    fontSize: 28,
    bold: true,
    color: color(palette.ink, "181512"),
  });

  addText(slide, page.summary || "", {
    x: xIn(72),
    y: yIn(210),
    w: xIn(1180),
    h: yIn(48),
    fontFace: fonts.body || "Microsoft YaHei UI",
    fontSize: 14,
    color: color(palette.muted, "5C544D"),
  });

  const steps = Array.isArray(page.steps) ? page.steps.slice(0, 3) : [];
  steps.forEach((step, index) => {
    const left = 84 + index * 598;
    const top = 320;
    addPanel(
      slide,
      xIn(left),
      yIn(top),
      xIn(516),
      yIn(172),
      "FBF7F1",
      palette.line || "D8C9B8"
    );
    addAccentBar(slide, xIn(left), yIn(top), xIn(516), yIn(6), palette.accent || "8F2D1F");
    addText(slide, `0${index + 1}`, {
      x: xIn(left + 20),
      y: yIn(top + 22),
      w: xIn(48),
      h: yIn(28),
      fontFace: fonts.label || "Bahnschrift",
      fontSize: 18,
      bold: true,
      color: color(palette.accent, "8F2D1F"),
    });
    addText(slide, step.title || "", {
      x: xIn(left + 86),
      y: yIn(top + 22),
      w: xIn(392),
      h: yIn(30),
      fontFace: fonts.heading || "Microsoft YaHei UI",
      fontSize: 16,
      bold: true,
      color: color(palette.ink, "181512"),
    });
    addText(slide, step.body || "", {
      x: xIn(left + 20),
      y: yIn(top + 74),
      w: xIn(468),
      h: yIn(74),
      fontFace: fonts.body || "Microsoft YaHei UI",
      fontSize: 12,
      color: color(palette.muted, "5C544D"),
    });
    if (index < steps.length - 1) {
      slide.addShape(pptx.ShapeType.line, {
        x: xIn(left + 516),
        y: yIn(top + 84),
        w: xIn(54),
        h: 0,
        line: { color: color(palette.accent, "8F2D1F"), width: 2, beginArrowType: "none", endArrowType: "triangle" },
      });
    }
  });
}

function renderClosing(slide, page) {
  renderEyebrow(slide, page);

  addText(slide, page.heading || "", {
    x: xIn(72),
    y: yIn(122),
    w: xIn(1220),
    h: yIn(84),
    fontFace: fonts.heading || "Microsoft YaHei UI",
    fontSize: 29,
    bold: true,
    color: color(palette.ink, "181512"),
  });

  addText(slide, page.summary || "", {
    x: xIn(72),
    y: yIn(206),
    w: xIn(1180),
    h: yIn(48),
    fontFace: fonts.body || "Microsoft YaHei UI",
    fontSize: 14,
    color: color(palette.muted, "5C544D"),
  });

  addPanel(
    slide,
    xIn(72),
    yIn(286),
    xIn(1776),
    yIn(94),
    palette.paperStrong || "EBE1D3",
    palette.line || "D8C9B8"
  );
  addText(slide, "结论不是不看代码，而是先把验收体系做硬。", {
    x: xIn(110),
    y: yIn(316),
    w: xIn(1680),
    h: yIn(34),
    align: "center",
    fontFace: fonts.heading || "Microsoft YaHei UI",
    fontSize: 18,
    bold: true,
    color: color(palette.ink, "181512"),
  });

  const cards = Array.isArray(page.cards) ? page.cards.slice(0, 3) : [];
  cards.forEach((card, index) => {
    const left = 72 + index * 600;
    const top = 420;
    addPanel(
      slide,
      xIn(left),
      yIn(top),
      xIn(552),
      yIn(138),
      "FBF7F1",
      palette.line || "D8C9B8"
    );
    addAccentBar(slide, xIn(left), yIn(top), xIn(552), yIn(5), index === 1 ? (palette.ink || "181512") : (palette.accent || "8F2D1F"));
    addText(slide, card.title || "", {
      x: xIn(left + 18),
      y: yIn(top + 18),
      w: xIn(512),
      h: yIn(28),
      fontFace: fonts.heading || "Microsoft YaHei UI",
      fontSize: 15,
      bold: true,
      color: color(palette.ink, "181512"),
    });
    addText(slide, card.body || "", {
      x: xIn(left + 18),
      y: yIn(top + 56),
      w: xIn(512),
      h: yIn(56),
      fontFace: fonts.body || "Microsoft YaHei UI",
      fontSize: 11.5,
      color: color(palette.muted, "5C544D"),
    });
  });
}

function renderSlide(slide, page) {
  slide.background = { color: color(palette.paper, "F4EFE6") };
  renderFrame(slide);

  switch (page.template) {
    case "cover":
      renderCover(slide, page);
      break;
    case "three-up":
      renderCardGrid(slide, page, 3);
      break;
    case "four-up":
      renderCardGrid(slide, page, 4);
      break;
    case "pillars":
      renderPillars(slide, page);
      break;
    case "comparison":
      renderComparison(slide, page);
      break;
    case "process-flow":
      renderProcessFlow(slide, page);
      break;
    case "closing":
      renderClosing(slide, page);
      break;
    default:
      renderHeadlineBullets(slide, page);
      break;
  }

  renderFooter(slide, page);
}

for (const page of spec.pages || []) {
  const slide = pptx.addSlide();
  renderSlide(slide, page);
}

await pptx.writeFile({ fileName: outputPath });
console.log(`PptxGenJS wrote ${outputPath}`);
