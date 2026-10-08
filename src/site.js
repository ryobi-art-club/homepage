(function() {
  function cssEscape(value) {
    if (window.CSS && typeof window.CSS.escape === 'function') return window.CSS.escape(value);
    return String(value).replace(/[^a-zA-Z0-9_-]/g, function(ch) { return '\\' + ch; });
  }
  function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }

  var Lightbox = {
    openTrigger: function() {}
  };

  function initReveals() {
    if (!('IntersectionObserver' in window)) return;
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    // 巨大なコンテナ(タブ枠など)は対象にしない。親が透明なままだと
    // 中身が丸ごと隠れて、出現がスクロールに対して遅く感じられるため。
    var targets = Array.from(document.querySelectorAll(
      '.section-header, .simple-card, .article-card, .request-card, .info-point, .timeline-item, .work-card'
    ));
    targets.forEach(function(el) {
      el.classList.add('reveal');
      var index = 0;
      var sibling = el;
      while ((sibling = sibling.previousElementSibling)) {
        if (sibling.classList.contains('reveal')) index++;
      }
      el.style.transitionDelay = Math.min(index, 7) * 70 + 'ms';
    });
    var observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        el.classList.add('is-visible');
        observer.unobserve(el);
        // 出現後は reveal を外す。inline の transition-delay を残すと
        // ホバー演出まで巻き添えで遅延するため。
        el.addEventListener('transitionend', function handle(event) {
          if (event.target !== el) return;
          el.removeEventListener('transitionend', handle);
          el.classList.remove('reveal', 'is-visible');
          el.style.transitionDelay = '';
        });
      });
    }, { threshold: 0, rootMargin: '0px 0px -48px 0px' });
    targets.forEach(function(el) { observer.observe(el); });
    // 保険: 初期表示でIntersectionObserverが発火しない環境でも、
    // 画面内の要素は一定時間後に必ず表示する。
    window.setTimeout(function() {
      targets.forEach(function(el) {
        if (!el.classList.contains('reveal') || el.classList.contains('is-visible')) return;
        var rect = el.getBoundingClientRect();
        if (rect.top < window.innerHeight && rect.bottom > 0) el.classList.add('is-visible');
      });
    }, 1500);
  }

  function initHeroSlideshow() {
    var root = document.querySelector('[data-hero-slideshow]');
    if (!root) return;
    var slides = Array.from(root.querySelectorAll('.hero-slide'));
    if (slides.length < 2) return;
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    // 2枚目以降は表示が近づいてから読み込む(全作品を並べても初期コストを増やさない)
    function ensureLoaded(slideIndex) {
      var img = slides[slideIndex] && slides[slideIndex].querySelector('img');
      if (!img) return;
      var src = img.getAttribute('data-src');
      if (src && !img.getAttribute('src')) {
        img.setAttribute('src', src);
        img.removeAttribute('data-src');
      }
    }
    var index = 0;
    ensureLoaded(1);
    window.setInterval(function() {
      if (document.hidden) return;
      index = (index + 1) % slides.length;
      ensureLoaded(index);
      ensureLoaded((index + 1) % slides.length);
      slides.forEach(function(slide, slideIndex) {
        slide.classList.toggle('is-active', slideIndex === index);
      });
    }, 5600);
  }

  function initMaterialChips() {
    var note = document.getElementById('materialNote');
    if (!note) return;
    var chips = Array.from(document.querySelectorAll('.material-chip.has-note'));
    var stickyChip = null;

    function renderNote(chip) {
      note.textContent = '';
      if (!chip) {
        note.hidden = true;
        return;
      }
      var name = document.createElement('strong');
      name.textContent = chip.getAttribute('data-name') || '';
      note.appendChild(name);
      note.appendChild(document.createTextNode('　' + (chip.getAttribute('data-note') || '')));
      note.hidden = false;
    }
    function setSticky(chip) {
      stickyChip = chip;
      chips.forEach(function(other) {
        other.classList.toggle('is-active', other === chip);
        other.setAttribute('aria-expanded', other === chip ? 'true' : 'false');
      });
      renderNote(chip);
    }

    chips.forEach(function(chip) {
      chip.addEventListener('click', function() {
        setSticky(chip === stickyChip ? null : chip);
      });
    });
    // ホバーできる環境では、乗せるだけで注釈をプレビューする(クリックで固定)。
    // 離れたときは固定中の注釈に戻す。固定が無ければ直前の表示を残して
    // レイアウトの上下動を減らす。
    if (window.matchMedia && window.matchMedia('(hover: hover)').matches) {
      chips.forEach(function(chip) {
        chip.addEventListener('mouseenter', function() { renderNote(chip); });
        chip.addEventListener('mouseleave', function() {
          if (stickyChip) renderNote(stickyChip);
        });
      });
    }
  }

  function initTabs() {
    document.querySelectorAll('[data-tab-shell]').forEach(function(shell) {
      var buttons = shell.querySelectorAll('[data-tab-target]');
      var panels = shell.querySelectorAll('[data-tab-panel]');
      function activate(id) {
        buttons.forEach(function(btn) {
          btn.classList.toggle('is-active', btn.getAttribute('data-tab-target') === id);
        });
        panels.forEach(function(panel) {
          panel.classList.toggle('is-active', panel.getAttribute('data-tab-panel') === id);
        });
      }
      buttons.forEach(function(btn) {
        btn.addEventListener('click', function() { activate(btn.getAttribute('data-tab-target')); });
      });
      if (buttons.length) activate(buttons[0].getAttribute('data-tab-target'));
    });
  }

  function initLightbox() {
    var overlay = document.createElement('div');
    overlay.className = 'lightbox';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.innerHTML = [
      '<button class="lightbox-close" type="button" aria-label="閉じる"><i class="fa-solid fa-xmark"></i></button>',
      '<button class="lightbox-button prev" type="button" aria-label="前へ"><i class="fa-solid fa-chevron-left"></i></button>',
      '<div class="lightbox-stage"><div class="lightbox-slider"><div class="lightbox-track"></div></div><div class="lightbox-caption"></div></div>',
      '<button class="lightbox-button next" type="button" aria-label="次へ"><i class="fa-solid fa-chevron-right"></i></button>'
    ].join('');
    document.body.appendChild(overlay);

    var slider = overlay.querySelector('.lightbox-slider');
    var track = overlay.querySelector('.lightbox-track');
    var caption = overlay.querySelector('.lightbox-caption');
    var close = overlay.querySelector('.lightbox-close');
    var prev = overlay.querySelector('.lightbox-button.prev');
    var next = overlay.querySelector('.lightbox-button.next');
    var state = { gallery: '', index: 0, items: [], dragging: false, moved: false, startX: 0, currentX: 0, pointerId: null };

    function collect(gallery) {
      return Array.from(document.querySelectorAll('[data-lightbox-gallery="' + cssEscape(gallery) + '"]')).map(function(button) {
        var img = button.querySelector('img');
        return {
          index: Number(button.getAttribute('data-lightbox-index') || 0),
          src: img ? img.getAttribute('src') : '',
          alt: img ? img.getAttribute('alt') || '' : '',
          caption: button.getAttribute('data-lightbox-caption') || (img ? img.getAttribute('alt') || '' : '')
        };
      }).sort(function(a, b) { return a.index - b.index; });
    }

    function buildSlides() {
      track.innerHTML = state.items.map(function(item) {
        return '<div class="lightbox-slide"><img src="' + item.src + '" alt="' + (item.alt || '') + '" draggable="false"></div>';
      }).join('');
    }

    function render(withTransition, offsetPercent) {
      var offset = typeof offsetPercent === 'number' ? offsetPercent : 0;
      track.style.transition = withTransition === false ? 'none' : 'transform 0.34s cubic-bezier(.22,.61,.36,1)';
      track.style.transform = 'translate3d(' + ((-100 * state.index) + offset) + '%,0,0)';
      var item = state.items[state.index];
      caption.textContent = item ? ((state.index + 1) + ' / ' + state.items.length + (item.caption ? '　' + item.caption : '')) : '';
      prev.disabled = state.index === 0;
      next.disabled = state.index === state.items.length - 1;
    }

    function open(gallery, index) {
      state.items = collect(gallery);
      if (!state.items.length) return;
      state.gallery = gallery;
      state.index = clamp(Number(index) || 0, 0, state.items.length - 1);
      buildSlides();
      render(false, 0);
      overlay.classList.add('is-open');
      document.body.classList.add('is-lightbox-open');
    }

    function openTrigger(trigger) {
      if (!trigger || !trigger.hasAttribute('data-lightbox-gallery')) return;
      open(trigger.getAttribute('data-lightbox-gallery'), trigger.getAttribute('data-lightbox-index') || 0);
    }
    Lightbox.openTrigger = openTrigger;
    window.RyobiLightbox = Lightbox;

    function closeBox() {
      overlay.classList.remove('is-open');
      document.body.classList.remove('is-lightbox-open');
      state.dragging = false;
      state.pointerId = null;
    }
    function moveBy(delta) {
      if (!state.items.length) return;
      state.index = Math.max(0, Math.min(state.items.length - 1, state.index + delta));
      render(true, 0);
    }
    function begin(event) {
      if (event.pointerType === 'mouse' && event.button !== 0) return;
      state.dragging = true;
      state.moved = false;
      state.startX = state.currentX = event.clientX;
      state.pointerId = event.pointerId;
      render(false, 0);
      if (slider.setPointerCapture) { try { slider.setPointerCapture(event.pointerId); } catch(e) {} }
    }
    function move(event) {
      if (!state.dragging || event.pointerId !== state.pointerId) return;
      state.currentX = event.clientX;
      var delta = state.currentX - state.startX;
      if (Math.abs(delta) > 6) state.moved = true;
      if ((state.index === 0 && delta > 0) || (state.index === state.items.length - 1 && delta < 0)) delta = delta / 3;
      render(false, delta / Math.max(slider.clientWidth, 1) * 100);
    }
    function end(event) {
      if (!state.dragging || event.pointerId !== state.pointerId) return;
      if (slider.releasePointerCapture) { try { slider.releasePointerCapture(event.pointerId); } catch(e) {} }
      var delta = state.currentX - state.startX;
      state.dragging = false;
      state.pointerId = null;
      if (Math.abs(delta) > 42) moveBy(delta < 0 ? 1 : -1);
      else render(true, 0);
    }

    document.addEventListener('click', function(event) {
      var trigger = event.target.closest && event.target.closest('[data-lightbox-gallery]');
      if (!trigger) return;
      var carousel = trigger.closest('[data-carousel]');
      if (carousel && carousel.dataset.suppressLightbox === 'true') return;
      event.preventDefault();
      event.stopPropagation();
      openTrigger(trigger);
    }, true);

    slider.addEventListener('pointerdown', begin);
    slider.addEventListener('pointermove', move);
    slider.addEventListener('pointerup', end);
    slider.addEventListener('pointercancel', end);
    close.addEventListener('click', function(event) { event.preventDefault(); event.stopPropagation(); closeBox(); });
    prev.addEventListener('click', function(event) { event.preventDefault(); event.stopPropagation(); moveBy(-1); });
    next.addEventListener('click', function(event) { event.preventDefault(); event.stopPropagation(); moveBy(1); });
    slider.addEventListener('click', function(event) { event.stopPropagation(); });
    overlay.addEventListener('click', function(event) { if (event.target === overlay) closeBox(); });
    document.addEventListener('keydown', function(event) {
      if (!overlay.classList.contains('is-open')) return;
      if (event.key === 'Escape') closeBox();
      if (event.key === 'ArrowLeft') moveBy(-1);
      if (event.key === 'ArrowRight') moveBy(1);
    });
  }

  function initCarousels() {
    document.querySelectorAll('[data-carousel]').forEach(function(root) {
      var track = root.querySelector('.carousel-track');
      var slides = Array.from(root.querySelectorAll('.carousel-slide'));
      var dots = Array.from(root.querySelectorAll('.carousel-dot'));
      var prev = root.querySelector('.carousel-button.prev');
      var next = root.querySelector('.carousel-button.next');
      if (!track || !slides.length) return;

      var index = 0;
      var dragging = false;
      var moved = false;
      var startX = 0;
      var startY = 0;
      var currentX = 0;
      var pointerId = null;
      var downTrigger = null;

      function render(withTransition, offsetPercent) {
        var offset = typeof offsetPercent === 'number' ? offsetPercent : 0;
        track.style.transition = withTransition === false ? 'none' : 'transform 0.34s cubic-bezier(.22,.61,.36,1)';
        track.style.transform = 'translate3d(' + ((-100 * index) + offset) + '%,0,0)';
        dots.forEach(function(dot, dotIndex) { dot.classList.toggle('is-active', dotIndex === index); });
        if (prev) prev.disabled = index === 0;
        if (next) next.disabled = index === slides.length - 1;
      }
      // ループさせない。末尾→先頭へ全スライドを逆走するアニメーションが
      // 不自然なため、端では止める。
      function setIndex(nextIndex) {
        index = Math.max(0, Math.min(slides.length - 1, nextIndex));
        render(true, 0);
      }
      function suppressClickBriefly() {
        root.dataset.suppressLightbox = 'true';
        window.setTimeout(function() { root.dataset.suppressLightbox = ''; }, 120);
      }
      function begin(event) {
        if (event.pointerType === 'mouse' && event.button !== 0) return;
        dragging = slides.length > 1;
        moved = false;
        startX = currentX = event.clientX;
        startY = event.clientY;
        pointerId = event.pointerId;
        downTrigger = event.target && event.target.closest ? event.target.closest('[data-lightbox-gallery]') : null;
        if (dragging) render(false, 0);
        if (track.setPointerCapture) { try { track.setPointerCapture(pointerId); } catch(e) {} }
      }
      function move(event) {
        if (event.pointerId !== pointerId) return;
        // 縦方向の動きが主なら「ページスクロールの意図」なのでタップ扱いしない
        var deltaY = event.clientY - startY;
        if (Math.abs(deltaY) > 10 && Math.abs(deltaY) > Math.abs(event.clientX - startX)) downTrigger = null;
        if (!dragging) return;
        currentX = event.clientX;
        var delta = currentX - startX;
        if (Math.abs(delta) > 8) moved = true;
        // 端を越える方向へのドラッグは抵抗を付ける
        if ((index === 0 && delta > 0) || (index === slides.length - 1 && delta < 0)) delta = delta / 3;
        render(false, delta / Math.max(root.clientWidth, 1) * 100);
      }
      function end(event) {
        if (pointerId !== null && event.pointerId !== pointerId) return;
        if (track.releasePointerCapture) { try { track.releasePointerCapture(pointerId); } catch(e) {} }
        if (dragging) {
          var delta = currentX - startX;
          if (Math.abs(delta) > 42) setIndex(index + (delta < 0 ? 1 : -1));
          else render(true, 0);
        }
        if (moved) {
          suppressClickBriefly();
        } else if (downTrigger && typeof Lightbox.openTrigger === 'function') {
          event.preventDefault();
          event.stopPropagation();
          Lightbox.openTrigger(downTrigger);
          suppressClickBriefly();
        }
        dragging = false;
        moved = false;
        pointerId = null;
        downTrigger = null;
      }
      // ブラウザがジェスチャーを引き取った(=縦スクロール開始など)ときは
      // タップ扱いせず状態だけ戻す。end に流すとライトボックスが誤って開く。
      function cancelPointer(event) {
        if (pointerId !== null && event.pointerId !== pointerId) return;
        if (track.releasePointerCapture) { try { track.releasePointerCapture(pointerId); } catch(e) {} }
        dragging = false;
        moved = false;
        pointerId = null;
        downTrigger = null;
        render(true, 0);
      }

      track.addEventListener('pointerdown', begin);
      track.addEventListener('pointermove', move);
      track.addEventListener('pointerup', end);
      track.addEventListener('pointercancel', cancelPointer);
      if (prev) prev.addEventListener('click', function(event) { event.preventDefault(); event.stopPropagation(); setIndex(index - 1); });
      if (next) next.addEventListener('click', function(event) { event.preventDefault(); event.stopPropagation(); setIndex(index + 1); });
      dots.forEach(function(dot, dotIndex) {
        dot.addEventListener('click', function(event) { event.preventDefault(); event.stopPropagation(); setIndex(dotIndex); });
      });
      render(true, 0);
    });
  }

  function initImageGrids() {
    document.querySelectorAll('.image-grid').forEach(function(grid) {
      var primary = grid.querySelector('.image-grid-item.is-primary img') || grid.querySelector('.image-grid-item img');
      if (!primary) return;
      function mark() {
        var ratio = (primary.naturalWidth || 1) / (primary.naturalHeight || 1);
        grid.classList.remove('primary-wide','primary-tall','primary-square','primary-very-wide');
        if (ratio >= 1.78) grid.classList.add('primary-very-wide');
        else if (ratio >= 1.18) grid.classList.add('primary-wide');
        else if (ratio <= 0.82) grid.classList.add('primary-tall');
        else grid.classList.add('primary-square');
      }
      if (primary.complete) mark(); else primary.addEventListener('load', mark, {once:true});
    });
  }

  // スクロールに連動するインク。ページの左右の端に一定間隔でインクを置き、
  // 画面に入ると弾けるように現れ、さらにスクロールすると下へ垂れていく。
  // 垂れた長さはその時点までの最大値を保ち、上に戻っても縮めない。
  // 形と配置は番号ごとに決まった乱数で作るので、いつ開いても同じになる。
  function initInkSplats() {
    var layer = document.querySelector('[data-ink-layer]');
    if (!layer) return;
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var SVG_NS = 'http://www.w3.org/2000/svg';
    var COLORS = ['ink-yellow', 'ink-green', 'ink-blue', 'ink-red'];
    var SPACING = 1000; // インク同士の縦の間隔(px)
    var splats = [], frame = 0, lastWidth = 0, lastHeight = 0;

    function seeded(seed) {
      return function() {
        seed = (seed + 0x6D2B79F5) | 0;
        var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
      };
    }
    function el(name, attrs) {
      var node = document.createElementNS(SVG_NS, name);
      Object.keys(attrs).forEach(function(key) { node.setAttribute(key, attrs[key]); });
      return node;
    }
    // 半径を揺らした点を閉じた曲線(Catmull-Rom)でつないで、いびつな円を作る
    function blobPath(cx, cy, r, rand) {
      var n = 11, pts = [];
      for (var i = 0; i < n; i++) {
        var angle = i / n * Math.PI * 2, rr = r * (0.8 + rand() * 0.35);
        pts.push([cx + Math.cos(angle) * rr, cy + Math.sin(angle) * rr]);
      }
      var d = 'M' + pts[0][0].toFixed(1) + ' ' + pts[0][1].toFixed(1);
      for (var k = 0; k < n; k++) {
        var p0 = pts[(k + n - 1) % n], p1 = pts[k], p2 = pts[(k + 1) % n], p3 = pts[(k + 2) % n];
        d += 'C' + (p1[0] + (p2[0] - p0[0]) / 6).toFixed(1) + ' ' + (p1[1] + (p2[1] - p0[1]) / 6).toFixed(1) +
          ' ' + (p2[0] - (p3[0] - p1[0]) / 6).toFixed(1) + ' ' + (p2[1] - (p3[1] - p1[1]) / 6).toFixed(1) +
          ' ' + p2[0].toFixed(1) + ' ' + p2[1].toFixed(1);
      }
      return d + 'Z';
    }

    function makeSplat(index, top, vw) {
      var rand = seeded(index * 977 + 13);
      var mobile = vw < 769;
      var r = (mobile ? 46 : 78) + rand() * (mobile ? 26 : 56);
      var pad = r * 0.6, maxDrip = (mobile ? 160 : 260) + rand() * (mobile ? 140 : 260);
      var width = (r + pad) * 2, height = (r + pad) * 2 + maxDrip;
      var cx = r + pad, cy = r + pad;
      var onLeft = index % 2 === 0;
      // 中心を画面の端付近に置き、半分以上を画面外に出して本文にかかりにくくする
      var centerX = onLeft ? r * (-0.35 + rand() * 0.4) : vw - r * (-0.35 + rand() * 0.4);
      var svg = el('svg', { width: width.toFixed(0), height: height.toFixed(0), viewBox: '0 0 ' + width.toFixed(1) + ' ' + height.toFixed(1) });
      svg.setAttribute('class', 'ink-splat ' + COLORS[index % COLORS.length]);
      svg.style.left = (centerX - cx).toFixed(1) + 'px';
      svg.style.top = (top - cy).toFixed(1) + 'px';

      // 筋はインクのうち画面に見えている部分からだけ垂らす(SVG内の座標で範囲を求める)
      var svgLeft = centerX - cx;
      var dripMin = Math.max(cx - r * 0.55, -svgLeft + 10);
      var dripMax = Math.min(cx + r * 0.55, vw - svgLeft - 10);
      var drips = [], count = 2 + Math.floor(rand() * 2);
      for (var i = 0; i < count; i++) {
        var w = r * (0.1 + rand() * 0.1), y0 = cy + r * 0.3;
        var x = dripMin + w / 2 + rand() * Math.max(0, dripMax - dripMin - w);
        var rect = el('rect', { x: (x - w / 2).toFixed(1), y: y0.toFixed(1), width: w.toFixed(1), height: '0', rx: (w / 2).toFixed(1) });
        var bulb = el('circle', { cx: x.toFixed(1), cy: y0.toFixed(1), r: (w * 0.7).toFixed(1) });
        svg.appendChild(rect);
        svg.appendChild(bulb);
        drips.push({ rect: rect, bulb: bulb, y0: y0, max: maxDrip * (0.35 + rand() * 0.65) });
      }
      var pop = el('g', { 'class': 'ink-pop' });
      pop.appendChild(el('path', { d: blobPath(cx, cy, r, rand) }));
      for (var s = 0, dots = 4 + Math.floor(rand() * 4); s < dots; s++) {
        var angle = rand() * Math.PI * 2, dist = r * (1.05 + rand() * 0.45);
        pop.appendChild(el('circle', {
          cx: (cx + Math.cos(angle) * dist).toFixed(1), cy: (cy + Math.sin(angle) * dist).toFixed(1),
          r: (r * (0.04 + rand() * 0.09)).toFixed(1)
        }));
      }
      svg.appendChild(pop);
      layer.appendChild(svg);
      return { svg: svg, pop: pop, top: top, drips: drips, splashed: false, progress: 0 };
    }

    function update(instant) {
      frame = 0;
      var vh = window.innerHeight, scrollY = window.scrollY;
      splats.forEach(function(splat) {
        var inView = splat.top - scrollY;
        if (!splat.splashed && inView < vh * 0.85) {
          splat.splashed = true;
          if (instant) splat.pop.style.transition = 'none';
          splat.svg.classList.add('is-splashed');
          if (instant) { splat.pop.getBoundingClientRect(); splat.pop.style.transition = ''; }
        }
        // 画面の下15%の位置で弾けてから、画面の高さ0.6枚分のスクロールで垂れきる。
        // 垂れている間はインクが画面内にあるので、伸びる様子が見える
        var progress = clamp((vh * 0.85 - inView) / (vh * 0.6), 0, 1);
        if (progress <= splat.progress) return;
        splat.progress = progress;
        var eased = 1 - Math.pow(1 - progress, 2);
        splat.drips.forEach(function(drip) {
          var length = drip.max * eased;
          drip.rect.setAttribute('height', length.toFixed(1));
          drip.bulb.setAttribute('cy', (drip.y0 + length).toFixed(1));
        });
      });
    }

    // ページの高さ(タブ切替で変わる)か幅が変わったら並べ直す。
    // 画面より上にあるインクは、垂れきった状態で即座に描き直す
    function build() {
      var vw = window.innerWidth, pageHeight = document.body.offsetHeight;
      if (vw === lastWidth && pageHeight === lastHeight) return;
      lastWidth = vw;
      lastHeight = pageHeight;
      layer.textContent = '';
      layer.style.height = pageHeight + 'px';
      var hero = document.querySelector('.hero-section');
      var start = (hero ? hero.offsetHeight : 0) + 260;
      splats = [];
      for (var i = 0, top = start; top < pageHeight - 200; i++, top += SPACING) {
        splats.push(makeSplat(i, top, vw));
      }
      update(true);
    }

    window.addEventListener('scroll', function() {
      if (!frame) frame = window.requestAnimationFrame(function() { update(false); });
    }, { passive: true });
    if ('ResizeObserver' in window) new ResizeObserver(build).observe(document.body);
    else window.addEventListener('resize', build);
    build();
  }

  document.addEventListener('DOMContentLoaded', function() {
    initReveals();
    initInkSplats();
    initHeroSlideshow();
    initMaterialChips();
    initTabs();
    initLightbox();
    initCarousels();
    initImageGrids();
  });
})();
