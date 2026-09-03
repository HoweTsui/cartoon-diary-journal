(function () {
  "use strict";

  var source = document.getElementById("diary-book-data");
  if (!source) {
    return;
  }

  var data;
  try {
    data = JSON.parse(source.textContent);
  } catch (error) {
    console.error("无法读取日记本数据", error);
    return;
  }

  var book = data.book;
  var periods = data.periods || [];
  var entries = data.entries || [];
  var characters = data.characters || [];
  var relationships = data.relationships || [];
  var bookPages = document.getElementById("book-pages");
  var pageStatus = document.getElementById("page-status");
  var timelineResults = document.getElementById("timeline-results");
  var characterResults = document.getElementById("character-results");
  var searchInput = document.getElementById("entry-search");
  var pageRecords = [];
  var pageIndexByEntry = new Map();
  var characterById = new Map(characters.map(function (character) {
    return [character.id, character];
  }));
  var entriesByPeriod = new Map(periods.map(function (period) {
    return [period.id, []];
  }));
  var entryCountByCharacter = new Map(characters.map(function (character) {
    return [character.id, 0];
  }));
  var reader = null;
  var pendingEntryId = null;
  var activeEntryId = null;
  var progressKey = "cartoon-diary-journal.book.v1." + book.id;

  entries.forEach(function (entry) {
    var group = entriesByPeriod.get(entry.periodId);
    if (group) {
      group.push(entry);
    }
    entry.characterIds.forEach(function (characterId) {
      entryCountByCharacter.set(
        characterId,
        (entryCountByCharacter.get(characterId) || 0) + 1
      );
    });
  });

  function create(tagName, className, text) {
    var element = document.createElement(tagName);
    if (className) {
      element.className = className;
    }
    if (text !== undefined && text !== null) {
      element.textContent = text;
    }
    return element;
  }

  function createPage(kind, density) {
    var page = create("article", "book-page " + kind);
    if (density) {
      page.dataset.density = density;
    }
    var inner = create("div", "page-inner");
    page.appendChild(inner);
    bookPages.appendChild(page);
    pageRecords.push({ kind: kind, entryId: null, title: "" });
    return { page: page, inner: inner, record: pageRecords[pageRecords.length - 1] };
  }

  function addText(container, tagName, className, text) {
    var element = create(tagName, className, text);
    container.appendChild(element);
    return element;
  }

  function graphHref(characterId) {
    return book.graphHref + "?character=" + encodeURIComponent(characterId);
  }

  function safeCoverPosition(value) {
    if (typeof value !== "string") {
      return "50% 50%";
    }
    var position = value.trim();
    return /^(?:0|[1-9]\d?|100)%\s+(?:0|[1-9]\d?|100)%$/.test(position)
      ? position
      : "50% 50%";
  }

  function addCoverMask(container) {
    var defsSvg = createSvgElement("svg");
    defsSvg.setAttribute("class", "cover-mask-defs");
    defsSvg.setAttribute("aria-hidden", "true");
    defsSvg.setAttribute("width", "0");
    defsSvg.setAttribute("height", "0");
    var defs = createSvgElement("defs");
    var clip = createSvgElement("clipPath");
    clip.setAttribute("id", "cover-mask-paper-days-2026");
    clip.setAttribute("clipPathUnits", "objectBoundingBox");
    var path = createSvgElement("path");
    path.setAttribute(
      "d",
      "M.08 .04C.18 .01 .31 .06 .42 .035C.57 .005 .75 .02 .92 .075 " +
      "L.96 .2C.93 .32 .99 .44 .95 .56C.99 .7 .91 .82 .94 .95 " +
      "C.78 .98 .64 .94 .5 .97C.34 .95 .2 .99 .07 .94 " +
      "C.1 .82 .03 .7 .07 .57C.02 .43 .09 .3 .05 .17Z"
    );
    defsSvg.appendChild(defs);
    defs.appendChild(clip);
    clip.appendChild(path);
    container.appendChild(defsSvg);
  }

  function addCoverPlaceholder(container) {
    var svg = createSvgElement("svg");
    svg.setAttribute("class", "cover-placeholder");
    svg.setAttribute("viewBox", "0 0 240 300");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "等待放入封面图的原创线稿占位图");
    var body = createSvgElement("path");
    body.setAttribute("d", "M83 165c-8-46 19-82 67-82 48 0 74 38 66 84-7 40-37 63-71 63-33 0-55-22-62-65Z");
    var hair = createSvgElement("path");
    hair.setAttribute("d", "M85 123c6-36 38-55 70-45 18 6 30 18 38 36l-19-8 5 16-22-8 2 18-25-14-10 18-17-12-9 13Z");
    hair.classList.add("solid");
    var eyeOne = createSvgElement("circle");
    eyeOne.setAttribute("cx", "124");
    eyeOne.setAttribute("cy", "145");
    eyeOne.setAttribute("r", "5");
    eyeOne.classList.add("solid");
    var eyeTwo = createSvgElement("circle");
    eyeTwo.setAttribute("cx", "158");
    eyeTwo.setAttribute("cy", "145");
    eyeTwo.setAttribute("r", "5");
    eyeTwo.classList.add("solid");
    var nose = createSvgElement("path");
    nose.setAttribute("d", "M119 157c-10 0-15 6-14 12 1 6 8 9 17 8");
    var mouth = createSvgElement("path");
    mouth.setAttribute("d", "M132 184h19");
    var shoulders = createSvgElement("path");
    shoulders.setAttribute("d", "M78 245c26-24 91-25 117 0v35H78Z");
    var armLeft = createSvgElement("path");
    armLeft.setAttribute("d", "M83 251l-18 38");
    var armRight = createSvgElement("path");
    armRight.setAttribute("d", "M190 251l18 38");
    [body, hair, eyeOne, eyeTwo, nose, mouth, shoulders, armLeft, armRight].forEach(function (element) {
      svg.appendChild(element);
    });
    container.appendChild(svg);
  }

  function addCover() {
    var rendered = createPage("cover", "hard");
    rendered.record.title = book.coverTitle || book.title;
    rendered.page.classList.add("cover-theme-" + (book.coverTheme || "brick"));
    var header = create("header", "cover-header");
    addText(header, "p", "cover-eyebrow", book.coverEyebrow || "OFFLINE DIARY");
    addText(header, "h2", "cover-title", book.coverTitle || book.title);
    if (book.coverSubtitle || book.subtitle) {
      addText(header, "p", "cover-subtitle", book.coverSubtitle || book.subtitle);
    }
    rendered.inner.appendChild(header);

    var art = create("div", "cover-art");
    addCoverMask(art);
    var paper = create("div", "cover-paper");
    var coverImageSource = book.coverImageSrc || book.coverSrc;
    if (coverImageSource) {
      var coverImage = create("img", "cover-image");
      coverImage.src = coverImageSource;
      coverImage.alt = book.coverImageAlt || ((book.coverTitle || book.title) + "封面主视觉");
      coverImage.style.objectPosition = safeCoverPosition(book.coverImagePosition);
      coverImage.loading = "eager";
      paper.appendChild(coverImage);
    } else {
      addCoverPlaceholder(paper);
    }
    art.appendChild(paper);
    var tapeLeft = create("span", "cover-tape cover-tape-left");
    tapeLeft.setAttribute("aria-hidden", "true");
    var tapeRight = create("span", "cover-tape cover-tape-right");
    tapeRight.setAttribute("aria-hidden", "true");
    art.appendChild(tapeLeft);
    art.appendChild(tapeRight);
    rendered.inner.appendChild(art);

    var coverYear = entries.length ? entries[0].date.slice(0, 4) : "";
    var volume = periods.length < 10 ? "0" + periods.length : String(periods.length);
    var metaRow = create("div", "cover-meta-row");
    addText(metaRow, "p", "cover-meta", (coverYear ? coverYear + "  ·  " : "") + "VOL. " + volume);
    rendered.inner.appendChild(metaRow);
  }

  function addTitlePage() {
    var rendered = createPage("title-page");
    rendered.record.title = "扉页";
    addText(rendered.inner, "p", "page-type", "DIARY BOOK");
    addText(rendered.inner, "h2", "", book.title);
    addText(
      rendered.inner,
      "p",
      "",
      book.subtitle || "把每一天留在一页纸上，也留在可以翻阅的时间里。"
    );
  }

  function pageButton(label, target, className) {
    var button = create("button", className || "page-link", label);
    button.type = "button";
    if (typeof target === "string") {
      button.dataset.entryId = target;
    }
    button.addEventListener("click", function () {
      var pageIndex = typeof target === "string" ? pageIndexByEntry.get(target) : target;
      goToPage(pageIndex, true);
    });
    return button;
  }

  function addContentsPage() {
    var rendered = createPage("toc-page");
    rendered.record.title = "目录";
    addText(rendered.inner, "p", "page-type", "CONTENTS");
    addText(rendered.inner, "h2", "", "目录");
    addText(rendered.inner, "p", "toc-description", "从时期进入，也可以在时间索引中直接寻找某一天。");
    var groups = create("div", "toc-groups");
    rendered.inner.appendChild(groups);
    periods.forEach(function (period) {
      var group = create("section", "toc-group");
      addText(group, "h3", "", period.title);
      var list = create("ul", "toc-list");
      (entriesByPeriod.get(period.id) || []).forEach(function (entry) {
        var item = create("li");
        var button = pageButton(entry.date + "　" + entry.title, entry.id);
        item.appendChild(button);
        list.appendChild(item);
      });
      group.appendChild(list);
      groups.appendChild(group);
    });
  }

  function relationshipSummary(characterId) {
    var labels = relationships.filter(function (relationship) {
      return relationship.source === characterId || relationship.target === characterId;
    }).map(function (relationship) {
      var otherId = relationship.source === characterId
        ? relationship.target
        : relationship.source;
      var other = characterById.get(otherId);
      return (other ? other.name : otherId) + "：" + relationship.label;
    });
    return labels.length ? labels.join("；") : "暂无已记录关系";
  }

  function characterCard(character, compact) {
    var card = create("a", compact ? "character-card-link" : "character-result");
    card.href = graphHref(character.id);
    card.title = "打开 " + character.name + " 的人物关系图";
    var avatar = create("img", "character-avatar");
    avatar.src = character.avatarSrc;
    avatar.alt = character.name + "头像";
    avatar.loading = "lazy";
    card.appendChild(avatar);
    var copy = create("div", "character-copy");
    addText(copy, "strong", "character-name", character.name);
    addText(copy, "span", "character-role", character.role || "人物角色");
    var anchors = Array.isArray(character.anchors) ? character.anchors : [];
    addText(
      copy,
      "p",
      "character-anchor",
      "外观：" + (anchors.length ? anchors.join("；") : "未填写")
    );
    addText(copy, "p", "character-anchor", "关系：" + relationshipSummary(character.id));
    addText(
      copy,
      "span",
      "character-count",
      "关联日记 " + (entryCountByCharacter.get(character.id) || 0) + " 篇"
    );
    card.appendChild(copy);
    return card;
  }

  function addCharacterDirectory() {
    var rendered = createPage("character-directory");
    rendered.record.title = "人物介绍";
    addText(rendered.inner, "p", "page-type", "CHARACTERS");
    addText(rendered.inner, "h2", "", "人物介绍");
    var grid = create("div", "character-grid");
    characters.forEach(function (character) {
      grid.appendChild(characterCard(character, true));
    });
    rendered.inner.appendChild(grid);
  }

  function createSvgElement(name) {
    return document.createElementNS("http://www.w3.org/2000/svg", name);
  }

  function addRelationshipOverview() {
    var rendered = createPage("relationship-overview");
    rendered.record.title = "人物关系";
    addText(rendered.inner, "p", "page-type", "RELATIONSHIP OVERVIEW");
    addText(rendered.inner, "h2", "", "人物关系");
    var map = create("div", "relationship-map");
    var svg = createSvgElement("svg");
    svg.setAttribute("viewBox", "0 0 320 250");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "人物关系概览");
    var positions = new Map();
    var radius = Math.max(66, Math.min(98, characters.length * 11));
    characters.forEach(function (character, index) {
      var angle = (-Math.PI / 2) + (Math.PI * 2 * index / Math.max(characters.length, 1));
      positions.set(character.id, {
        x: 160 + Math.cos(angle) * radius,
        y: 125 + Math.sin(angle) * radius
      });
    });
    relationships.forEach(function (relationship) {
      var source = positions.get(relationship.source);
      var target = positions.get(relationship.target);
      if (!source || !target) {
        return;
      }
      var line = createSvgElement("line");
      line.setAttribute("x1", source.x);
      line.setAttribute("y1", source.y);
      line.setAttribute("x2", target.x);
      line.setAttribute("y2", target.y);
      svg.appendChild(line);
    });
    characters.forEach(function (character) {
      var position = positions.get(character.id);
      var group = createSvgElement("a");
      group.setAttribute("href", graphHref(character.id));
      group.setAttribute("aria-label", "打开 " + character.name + " 的人物关系图");
      group.setAttribute("tabindex", "0");
      var title = createSvgElement("title");
      title.textContent = "打开 " + character.name + " 的人物关系图";
      group.appendChild(title);
      var circle = createSvgElement("circle");
      circle.setAttribute("cx", position.x);
      circle.setAttribute("cy", position.y);
      circle.setAttribute("r", "22");
      group.appendChild(circle);
      var text = createSvgElement("text");
      text.setAttribute("x", position.x);
      text.setAttribute("y", position.y + 4);
      text.textContent = character.name.slice(0, 4);
      group.appendChild(text);
      svg.appendChild(group);
    });
    map.appendChild(svg);
    rendered.inner.appendChild(map);
    var actions = create("div", "relationship-actions");
    var link = create("a", "graph-link", "打开完整人物关系图");
    link.href = book.graphHref;
    actions.appendChild(link);
    rendered.inner.appendChild(actions);
  }

  function addBlankPage() {
    var rendered = createPage("blank-page");
    rendered.record.title = "留白";
  }

  function addPeriodPage(period) {
    var rendered = createPage("period-page");
    rendered.record.title = period.title;
    var art = create("div", "period-art");
    if (period.coverSrc) {
      var image = create("img", "period-image");
      image.src = period.coverSrc;
      image.alt = period.title + "时期插画";
      image.loading = "lazy";
      art.appendChild(image);
    }
    addText(rendered.inner, "p", "page-type", period.startDate + " — " + period.endDate);
    addText(rendered.inner, "h2", "", period.title);
    if (period.summary) {
      addText(rendered.inner, "p", "", period.summary);
    }
    if (period.coverSrc) {
      rendered.inner.appendChild(art);
    }
  }

  function addEntryPage(entry) {
    var rendered = createPage("entry-page");
    rendered.record.entryId = entry.id;
    rendered.record.title = entry.title;
    pageIndexByEntry.set(entry.id, pageRecords.length - 1);
    var posterWrap = create("div", "entry-poster-wrap");
    var poster = create("img", "entry-poster");
    poster.src = entry.posterSrc;
    poster.alt = entry.date + " " + entry.title + " 日记海报";
    poster.loading = "lazy";
    posterWrap.appendChild(poster);
    rendered.inner.appendChild(posterWrap);
    var metadata = create("footer", "entry-meta");
    var copy = create("div", "entry-copy");
    addText(copy, "p", "entry-summary", entry.summary);
    var footer = create("div", "entry-footer");
    entry.tags.forEach(function (tag) {
      addText(footer, "span", "entry-tag", tag);
    });
    entry.characterIds.forEach(function (characterId) {
      var character = characterById.get(characterId);
      if (character) {
        var link = create("a", "entry-tag", character.name);
        link.href = graphHref(characterId);
        footer.appendChild(link);
      }
    });
    copy.appendChild(footer);
    metadata.appendChild(copy);
    addText(metadata, "p", "entry-folio", "第 " + pageRecords.length + " 页");
    rendered.inner.appendChild(metadata);
  }

  function addIndexPage() {
    var rendered = createPage("index-page");
    rendered.record.title = "日记索引";
    addText(rendered.inner, "p", "page-type", "DIARY INDEX");
    addText(rendered.inner, "h2", "", "日记索引");
    var groups = create("div", "index-groups");
    periods.forEach(function (period) {
      var group = create("section", "index-group");
      addText(group, "h3", "", period.title);
      var list = create("ul", "index-list");
      (entriesByPeriod.get(period.id) || []).forEach(function (entry) {
        var item = create("li");
        item.appendChild(pageButton(entry.date + "　" + entry.title, entry.id));
        list.appendChild(item);
      });
      group.appendChild(list);
      groups.appendChild(group);
    });
    rendered.inner.appendChild(groups);
  }

  function addBackCover() {
    var rendered = createPage("back-cover", "hard");
    rendered.record.title = "封底";
    addText(rendered.inner, "p", "cover-label", "THE END, FOR NOW");
    addText(rendered.inner, "p", "", "下一页，留给明天。 ");
  }

  function buildPages() {
    addCover();
    addTitlePage();
    addContentsPage();
    addCharacterDirectory();
    addRelationshipOverview();
    periods.forEach(function (period) {
      if (pageRecords.length % 2 === 1) {
        addBlankPage();
      }
      addPeriodPage(period);
      (entriesByPeriod.get(period.id) || []).forEach(addEntryPage);
    });
    addIndexPage();
    addBackCover();
  }

  function characterSearchText(entry) {
    return entry.characterIds.map(function (characterId) {
      var character = characterById.get(characterId);
      return character ? (character.name + " " + character.role) : "";
    }).join(" ");
  }

  function renderTimeline(query) {
    timelineResults.textContent = "";
    var term = (query || "").trim().toLocaleLowerCase();
    var matching = entries.filter(function (entry) {
      if (!term) {
        return true;
      }
      return [
        entry.date,
        entry.title,
        entry.summary,
        entry.tags.join(" "),
        characterSearchText(entry)
      ].join(" ").toLocaleLowerCase().indexOf(term) !== -1;
    });
    if (!matching.length) {
      addText(timelineResults, "p", "character-anchor", "没有找到匹配日记。");
      return;
    }
    matching.forEach(function (entry) {
      var button = create("button", "timeline-result");
      button.type = "button";
      button.dataset.entryId = entry.id;
      addText(button, "strong", "", entry.date + "　" + entry.title);
      addText(button, "span", "", entry.summary);
      button.addEventListener("click", function () {
        showPanel("reader");
        goToPage(pageIndexByEntry.get(entry.id), true);
      });
      timelineResults.appendChild(button);
    });
  }

  function renderCharacters() {
    characterResults.textContent = "";
    characters.forEach(function (character) {
      characterResults.appendChild(characterCard(character, false));
    });
  }

  function entryIdFromHash() {
    var match = /^#entry=([^&]+)$/.exec(window.location.hash);
    if (!match) {
      return null;
    }
    try {
      return decodeURIComponent(match[1]);
    } catch (error) {
      return null;
    }
  }

  function pageIndexFromHash() {
    var match = /^#page=(\d+)$/.exec(window.location.hash);
    if (!match) {
      return null;
    }
    var pageIndex = Number(match[1]) - 1;
    return Number.isInteger(pageIndex) && pageIndex >= 0 && pageIndex < pageRecords.length
      ? pageIndex
      : null;
  }

  function storedEntryId() {
    try {
      var saved = JSON.parse(window.localStorage.getItem(progressKey));
      return saved && typeof saved.entryId === "string" ? saved.entryId : null;
    } catch (error) {
      return null;
    }
  }

  function visiblePageIndexes(pageIndex) {
    var first = Math.max(0, Math.min(pageIndex, pageRecords.length - 1));
    if (!reader || reader.getOrientation() !== "landscape" || first === 0) {
      return [first];
    }
    return first + 1 < pageRecords.length ? [first, first + 1] : [first];
  }

  function entryForVisiblePages(pageIndexes) {
    var visibleEntries = pageIndexes.map(function (index) {
      return pageRecords[index] && pageRecords[index].entryId;
    }).filter(Boolean);
    if (pendingEntryId && visibleEntries.indexOf(pendingEntryId) !== -1) {
      var focusedEntry = pendingEntryId;
      pendingEntryId = null;
      return focusedEntry;
    }
    if (activeEntryId && visibleEntries.indexOf(activeEntryId) !== -1) {
      return activeEntryId;
    }
    return visibleEntries[0] || null;
  }

  function updateEntryHighlight(entryId) {
    document.querySelectorAll("[data-entry-id]").forEach(function (element) {
      var selected = element.dataset.entryId === entryId;
      element.classList.toggle("is-current", selected);
      if (selected) {
        element.setAttribute("aria-current", "page");
      } else {
        element.removeAttribute("aria-current");
      }
    });
  }

  function setHash(hash) {
    if (window.location.hash !== hash) {
      window.history.replaceState(null, "", hash);
    }
  }

  function updatePageState(pageIndex) {
    var visibleIndexes = visiblePageIndexes(pageIndex);
    var focusedEntryId = entryForVisiblePages(visibleIndexes);
    var range = visibleIndexes.length === 2
      ? (visibleIndexes[0] + 1) + "–" + (visibleIndexes[1] + 1)
      : String(visibleIndexes[0] + 1);
    pageStatus.textContent = "第 " + range + " / " + pageRecords.length + " 页";
    activeEntryId = focusedEntryId;
    updateEntryHighlight(activeEntryId);
    if (activeEntryId) {
      try {
        window.localStorage.setItem(progressKey, JSON.stringify({ entryId: activeEntryId }));
      } catch (error) {
        // Reading progress is optional when browser storage is unavailable.
      }
      setHash("#entry=" + encodeURIComponent(activeEntryId));
    } else {
      setHash("#page=" + (visibleIndexes[0] + 1));
    }
  }

  function goToPage(pageIndex, animate) {
    if (typeof pageIndex !== "number" || pageIndex < 0 || pageIndex >= pageRecords.length) {
      return;
    }
    if (!reader) {
      return;
    }
    pendingEntryId = pageRecords[pageIndex].entryId || null;
    if (animate) {
      reader.flip(pageIndex, "top");
    } else {
      reader.turnToPage(pageIndex);
    }
    updatePageState(reader.getCurrentPageIndex());
  }

  function showPanel(name) {
    var timeline = document.getElementById("timeline-panel");
    var characterPanel = document.getElementById("characters-panel");
    timeline.hidden = name !== "timeline";
    characterPanel.hidden = name !== "characters";
    document.querySelectorAll(".nav-button").forEach(function (button) {
      button.classList.toggle("is-active", button.dataset.panel === name);
    });
  }

  function setupNavigation() {
    document.querySelectorAll(".nav-button").forEach(function (button) {
      button.addEventListener("click", function () {
        showPanel(button.dataset.panel || "reader");
      });
    });
    document.getElementById("previous-page").addEventListener("click", function () {
      if (reader) {
        reader.flipPrev("top");
      }
    });
    document.getElementById("next-page").addEventListener("click", function () {
      if (reader) {
        reader.flipNext("top");
      }
    });
    searchInput.addEventListener("input", function () {
      renderTimeline(searchInput.value);
    });
    window.addEventListener("hashchange", function () {
      var entryId = entryIdFromHash();
      if (entryId && pageIndexByEntry.has(entryId)) {
        goToPage(pageIndexByEntry.get(entryId), false);
        return;
      }
      var pageIndex = pageIndexFromHash();
      if (pageIndex !== null) {
        goToPage(pageIndex, false);
      }
    });
  }

  function startReader() {
    if (!window.St || !window.St.PageFlip) {
      bookPages.classList.add("fallback-book");
      pageStatus.textContent = "翻页组件不可用，已显示静态日记页。";
      return;
    }
    var initialEntry = entryIdFromHash() || storedEntryId();
    var initialPage = initialEntry && pageIndexByEntry.has(initialEntry)
      ? pageIndexByEntry.get(initialEntry)
      : (pageIndexFromHash() || 0);
    pendingEntryId = initialEntry && pageIndexByEntry.has(initialEntry) ? initialEntry : null;
    reader = new window.St.PageFlip(bookPages, {
      width: 450,
      height: 600,
      size: "stretch",
      minWidth: 240,
      maxWidth: 720,
      minHeight: 320,
      maxHeight: 960,
      showCover: true,
      usePortrait: true,
      drawShadow: true,
      maxShadowOpacity: 0.18,
      flippingTime: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 80 : 620,
      swipeDistance: 36,
      clickEventForward: true,
      mobileScrollSupport: true,
      disableFlipByClick: false,
      startPage: initialPage
    });
    reader.on("flip", function () {
      updatePageState(reader.getCurrentPageIndex());
    });
    reader.on("init", function () {
      updatePageState(reader.getCurrentPageIndex());
    });
    reader.on("changeOrientation", function () {
      updatePageState(reader.getCurrentPageIndex());
    });
    reader.loadFromHTML(document.querySelectorAll(".book-page"));
  }

  document.getElementById("book-title").textContent = book.title;
  buildPages();
  renderTimeline("");
  renderCharacters();
  setupNavigation();
  startReader();
}());
