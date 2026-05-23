// Shared navbar component — single source of truth for all pages.
// Usage: <div id="ty-navbar" data-page="help|about|"></div>
//        <script src="navbar.js"></script>

// Global analytics helper — available on all pages before any other script runs.
function tyTrack(event, params) {
  if (typeof gtag === 'function') gtag('event', event, params || {});
}

(function () {
  var container = document.getElementById('ty-navbar');
  if (!container) return;

  var page = container.dataset.page || '';

  function navLink(href, label, id) {
    var active = page === id ? ' active' : '';
    return '<li class="nav-item"><a class="nav-link' + active + '" href="' + href + '">' + label + '</a></li>';
  }

  container.innerHTML =
    '<nav class="navbar navbar-expand-md navbar-light sticky-top" style="background-color:#ffffff;">' +
      '<div class="container">' +
        '<a class="navbar-brand tickeryeti_brand" href="index.html">' +
          '<img src="./images/tickeryeti_face_brand.png" height="30" alt=""> TickerYeti' +
        '</a>' +
        '<button class="navbar-toggler" type="button" data-bs-toggle="collapse"' +
          ' data-bs-target="#navbarContent" aria-controls="navbarContent"' +
          ' aria-expanded="false" aria-label="Toggle navigation">' +
          '<span class="navbar-toggler-icon"></span>' +
        '</button>' +
        '<div class="collapse navbar-collapse" id="navbarContent">' +
          '<ul class="navbar-nav ms-auto">' +
            navLink('help.html', 'Help', 'help') +
            navLink('about.html', 'About', 'about') +
          '</ul>' +
          '<div class="d-flex align-items-center ms-3" title="Toggle dark mode">' +
            '<label class="ty-darkmode-switch">' +
              '<input type="checkbox" id="ty-darkmode-toggle" aria-label="Toggle dark mode">' +
              '<span class="ty-darkmode-slider"></span>' +
            '</label>' +
          '</div>' +
        '</div>' +
      '</div>' +
    '</nav>';

  // Apply body dark class immediately (html class already set by head script)
  if (localStorage.getItem('ty_dark') === '1') {
    document.body.classList.add('ty-dark');
  }

  // Wire up toggle
  var toggle = document.getElementById('ty-darkmode-toggle');
  if (toggle) {
    toggle.checked = localStorage.getItem('ty_dark') === '1';
    toggle.addEventListener('change', function () {
      var dark = toggle.checked;
      document.body.classList.toggle('ty-dark', dark);
      document.documentElement.classList.toggle('ty-dark', dark);
      localStorage.setItem('ty_dark', dark ? '1' : '0');
      tyTrack('dark_mode_toggled', { enabled: dark });
    });
  }
}());
