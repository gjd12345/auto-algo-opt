/* Zero-dependency Rich Markdown & Mathematical Formula Renderer. */
(function () {
  "use strict";

  function esc(val) {
    return String(val === null || val === undefined ? "" : val)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function convertLatexTokens(raw) {
    let s = esc(raw.trim());
    // Basic LaTeX macro replacements into clean Unicode + HTML sup/sub
    const pairs = [
      [/\\Phi/g, "&Phi;"],
      [/\\Delta/g, "&Delta;"],
      [/\\Sigma|\\sum/g, "&Sigma;"],
      [/\\alpha/g, "&alpha;"],
      [/\\beta/g, "&beta;"],
      [/\\gamma/g, "&gamma;"],
      [/\\delta/g, "&delta;"],
      [/\\epsilon|\\varepsilon/g, "&epsilon;"],
      [/\\theta/g, "&theta;"],
      [/\\lambda/g, "&lambda;"],
      [/\\mu/g, "&mu;"],
      [/\\nu/g, "&nu;"],
      [/\\rho/g, "&rho;"],
      [/\\sigma/g, "&sigma;"],
      [/\\tau/g, "&tau;"],
      [/\\ell/g, "&#8467;"],
      [/\\le|\\leq/g, "&le;"],
      [/\\ge|\\geq/g, "&ge;"],
      [/\\neq/g, "&ne;"],
      [/\\approx/g, "&asymp;"],
      [/\\times/g, "&times;"],
      [/\\cdot/g, "&middot;"],
      [/\\iff|\\Longleftrightarrow/g, "&hArr;"],
      [/\\to|\\rightarrow/g, "&rarr;"],
      [/\\in/g, "&isin;"],
      [/\\notin/g, "&notin;"],
      [/\\min/g, "min"],
      [/\\max/g, "max"],
      [/\\Pr/g, "Pr"],
      [/\\operatorname\{Var\}/g, "Var"],
      [/\\mathbb\{E\}/g, "E"],
      [/\\mathbf\{1\}/g, "1"],
      [/\\left/g, ""],
      [/\\right/g, ""],
      [/\\!/g, ""],
      [/\\;/g, " "]
    ];
    for (let i = 0; i < pairs.length; i++) {
      s = s.replace(pairs[i][0], pairs[i][1]);
    }
    s = s.replace(/\\text\{([^{}]+)\}/g, "$1");
    s = s.replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, "($1) / ($2)");
    s = s.replace(/\^\{([^{}]+)\}/g, "<sup>$1</sup>");
    s = s.replace(/_\{([^{}]+)\}/g, "<sub>$1</sub>");
    s = s.replace(/\^([A-Za-z0-9\-]+)/g, "<sup>$1</sup>");
    s = s.replace(/_([A-Za-z0-9]+)/g, "<sub>$1</sub>");
    return s;
  }

  function formatInline(text) {
    // Extract math segments before escaping rest
    const tokens = [];
    let str = String(text || "");
    str = str.replace(/\$([^$\n]+)\$/g, function (_, expr) {
      const idx = tokens.length;
      tokens.push('<span class="math-inline">' + convertLatexTokens(expr) + "</span>");
      return "\u0000M" + idx + "\u0000";
    });
    str = str.replace(/`([^`\n]+)`/g, function (_, code) {
      const idx = tokens.length;
      tokens.push('<code class="mono">' + esc(code) + "</code>");
      return "\u0000M" + idx + "\u0000";
    });
    str = esc(str);
    str = str.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
    str = str.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    str = str.replace(/\u0000M(\d+)\u0000/g, function (_, idx) {
      return tokens[Number(idx)] || "";
    });
    return str;
  }

  function isTableSep(line) {
    return /^\|?[\s:-]+\|[\s|:-]*$/.test(line.trim());
  }

  function splitTableRow(line) {
    let trimmed = line.trim();
    if (trimmed.startsWith("|")) trimmed = trimmed.slice(1);
    if (trimmed.endsWith("|")) trimmed = trimmed.slice(0, -1);
    return trimmed.split("|").map(function (c) { return c.trim(); });
  }

  function renderRichMarkdown(md) {
    const raw = String(md || "").replace(/\r\n/g, "\n").trim();
    if (!raw) return '<p class="muted">该条目暂无正文细则，请查看核心摘要与关联证据。</p>';

    // First replace display math blocks $$ ... $$
    const displayBlocks = [];
    const pre = raw.replace(/\$\$([\s\S]*?)\$\$/g, function (_, expr) {
      const idx = displayBlocks.length;
      displayBlocks.push('<div class="math-display">' + convertLatexTokens(expr) + "</div>");
      return "\n@@MATHBLOCK_" + idx + "@@\n";
    });

    const lines = pre.split("\n");
    const out = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];
      const trimmed = line.trim();

      if (!trimmed) { i++; continue; }

      // Drop redundant leading H1 matching card title
      if (i === 0 && trimmed.startsWith("# ")) { i++; continue; }

      const mathMatch = trimmed.match(/^@@MATHBLOCK_(\d+)@@$/);
      if (mathMatch) {
        out.push(displayBlocks[Number(mathMatch[1])] || "");
        i++;
        continue;
      }

      if (trimmed.startsWith("### ")) {
        out.push("<h3>" + formatInline(trimmed.slice(4)) + "</h3>");
        i++;
        continue;
      }
      if (trimmed.startsWith("## ")) {
        out.push("<h2>" + formatInline(trimmed.slice(3)) + "</h2>");
        i++;
        continue;
      }
      if (trimmed.startsWith("# ")) {
        out.push("<h2>" + formatInline(trimmed.slice(2)) + "</h2>");
        i++;
        continue;
      }

      // Blockquote
      if (trimmed.startsWith("> ")) {
        const qLines = [];
        while (i < lines.length && lines[i].trim().startsWith("> ")) {
          qLines.push(formatInline(lines[i].trim().slice(2)));
          i++;
        }
        out.push("<blockquote>" + qLines.join("<br>") + "</blockquote>");
        continue;
      }

      // Markdown table
      if (trimmed.includes("|") && i + 1 < lines.length && isTableSep(lines[i + 1])) {
        const headers = splitTableRow(trimmed);
        i += 2;
        const rows = [];
        while (i < lines.length && lines[i].trim().includes("|") && !lines[i].trim().startsWith("#")) {
          rows.push(splitTableRow(lines[i]));
          i++;
        }
        const th = headers.map(function (h) { return "<th>" + formatInline(h) + "</th>"; }).join("");
        const tb = rows.map(function (r) {
          return "<tr>" + r.map(function (c) { return "<td>" + formatInline(c) + "</td>"; }).join("") + "</tr>";
        }).join("");
        out.push("<table><thead><tr>" + th + "</tr></thead><tbody>" + tb + "</tbody></table>");
        continue;
      }

      // Unordered list
      if (/^[-*]\s+/.test(trimmed)) {
        const items = [];
        while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
          items.push("<li>" + formatInline(lines[i].trim().replace(/^[-*]\s+/, "")) + "</li>");
          i++;
        }
        out.push("<ul>" + items.join("") + "</ul>");
        continue;
      }

      // Ordered list
      if (/^\d+\.\s+/.test(trimmed)) {
        const items = [];
        while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
          items.push("<li>" + formatInline(lines[i].trim().replace(/^\d+\.\s+/, "")) + "</li>");
          i++;
        }
        out.push("<ol>" + items.join("") + "</ol>");
        continue;
      }

      // Fenced code blocks -> render softly as readable algorithm note rather than terminal raw box
      if (trimmed.startsWith("```")) {
        i++;
        const codeLines = [];
        while (i < lines.length && !lines[i].trim().startsWith("```")) {
          codeLines.push(lines[i]);
          i++;
        }
        if (i < lines.length) i++;
        out.push('<blockquote class="mono" style="background:var(--bg-parchment);border-left-color:var(--indigo);font-size:12.5px;white-space:pre-wrap;">' + esc(codeLines.join("\n")) + "</blockquote>");
        continue;
      }

      // Paragraph accumulation
      const pLines = [];
      while (
        i < lines.length &&
        lines[i].trim() &&
        !lines[i].trim().startsWith("#") &&
        !lines[i].trim().startsWith("> ") &&
        !/^[-*]\s+/.test(lines[i].trim()) &&
        !/^\d+\.\s+/.test(lines[i].trim()) &&
        !/^@@MATHBLOCK_\d+@@$/.test(lines[i].trim()) &&
        !(lines[i].trim().includes("|") && i + 1 < lines.length && isTableSep(lines[i + 1]))
      ) {
        pLines.push(formatInline(lines[i].trim()));
        i++;
      }
      out.push("<p>" + pLines.join(" ") + "</p>");
    }

    return '<div class="rich-md">' + out.join("\n") + "</div>";
  }

  window.KB_RENDERERS = {
    esc: esc,
    convertLatexTokens: convertLatexTokens,
    formatInline: formatInline,
    renderRichMarkdown: renderRichMarkdown
  };
})();
