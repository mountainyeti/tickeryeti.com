(function () {
  var API = 'https://0mzipto7d3.execute-api.us-east-1.amazonaws.com/feedback';

  // ── Inject modal HTML ───────────────────────────────────────────────────────
  var modalEl = document.createElement('div');
  modalEl.innerHTML =
    '<div class="modal fade" id="ty-feedback-modal" tabindex="-1"' +
        ' aria-labelledby="ty-feedback-title" aria-hidden="true">' +
      '<div class="modal-dialog modal-dialog-centered">' +
        '<div class="modal-content ty-modal">' +
          '<div class="modal-header">' +
            '<h5 class="modal-title" id="ty-feedback-title">Leave Feedback</h5>' +
            '<button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>' +
          '</div>' +
          '<div class="modal-body" id="ty-fb-body">' +
            '<p class="small mb-3 ty-fb-hint">Found a bug? Have a suggestion? We\'d love to hear from you.</p>' +
            '<form id="ty-fb-form" novalidate>' +
              '<input type="text" name="website" style="position:absolute;left:-9999px" tabindex="-1" autocomplete="off">' +
              '<div class="d-flex gap-2 mb-3" role="group" aria-label="Feedback type">' +
                '<input type="radio" class="btn-check" name="fb-type" id="fb-bug"        value="Bug Report"  autocomplete="off">' +
                '<label class="btn btn-sm btn-outline-light" for="fb-bug">Bug</label>' +
                '<input type="radio" class="btn-check" name="fb-type" id="fb-suggestion" value="Suggestion"  autocomplete="off">' +
                '<label class="btn btn-sm btn-outline-light" for="fb-suggestion">Suggestion</label>' +
                '<input type="radio" class="btn-check" name="fb-type" id="fb-other"      value="Other"       autocomplete="off" checked>' +
                '<label class="btn btn-sm btn-outline-light" for="fb-other">Other</label>' +
              '</div>' +
              '<textarea class="form-control ty-input mb-3" id="fb-message" rows="4"' +
                ' placeholder="What\'s on your mind?" maxlength="2000" required></textarea>' +
              '<div class="row g-2">' +
                '<div class="col">' +
                  '<input type="text"  class="form-control ty-input" id="fb-name"  placeholder="Name (optional)"  maxlength="100">' +
                '</div>' +
                '<div class="col">' +
                  '<input type="email" class="form-control ty-input" id="fb-email" placeholder="Email (optional)" maxlength="200">' +
                '</div>' +
              '</div>' +
            '</form>' +
          '</div>' +
          '<div class="modal-footer">' +
            '<button type="button" class="ty-link-btn" data-bs-dismiss="modal">Cancel</button>' +
            '<button type="button" class="ty-btn-yeti" id="ty-fb-submit" style="font-size:14px;padding:8px 22px">Send</button>' +
          '</div>' +
        '</div>' +
      '</div>' +
    '</div>';
  document.body.appendChild(modalEl.firstChild);

  // ── Submit handler ──────────────────────────────────────────────────────────
  document.getElementById('ty-feedback-modal').addEventListener('show.bs.modal', function () {
    tyTrack('feedback_opened');
  });

  document.getElementById('ty-fb-submit').addEventListener('click', function () {
    var message = (document.getElementById('fb-message').value || '').trim();
    if (!message) { document.getElementById('fb-message').focus(); return; }

    var type     = (document.querySelector('input[name="fb-type"]:checked') || {}).value || 'Other';
    var name     = (document.getElementById('fb-name').value  || '').trim();
    var email    = (document.getElementById('fb-email').value || '').trim();
    var honeypot = (document.querySelector('input[name="website"]').value || '');

    var btn = this;
    btn.disabled = true;
    btn.textContent = 'Sending…';

    fetch(API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: message, type: type, name: name, email: email, website: honeypot }),
    })
    .then(function (res) { if (!res.ok) throw new Error('server'); return res.json(); })
    .then(function () {
      tyTrack('feedback_submitted', { type: type });
      document.getElementById('ty-fb-body').innerHTML =
        '<div class="text-center py-3">' +
          '<p class="mb-1 fw-bold" style="font-size:18px">Thanks!</p>' +
          '<p class="mb-0 ty-fb-hint">Your feedback has been received.</p>' +
        '</div>';
      document.getElementById('ty-fb-submit').style.display = 'none';
    })
    .catch(function () {
      btn.disabled = false;
      btn.textContent = 'Send';
      var err = document.getElementById('ty-fb-err');
      if (!err) {
        err = document.createElement('p');
        err.id = 'ty-fb-err';
        err.className = 'small mt-2 mb-0';
        err.style.color = '#f87171';
        document.getElementById('ty-fb-body').appendChild(err);
      }
      err.textContent = 'Something went wrong — please try again.';
    });
  });

  // Reset form when modal closes
  document.getElementById('ty-feedback-modal').addEventListener('hidden.bs.modal', function () {
    document.getElementById('ty-fb-form') && document.getElementById('ty-fb-form').reset();
    document.getElementById('ty-fb-err')  && document.getElementById('ty-fb-err').remove();
    var btn = document.getElementById('ty-fb-submit');
    btn.disabled = false; btn.textContent = 'Send'; btn.style.display = '';
    var body = document.getElementById('ty-fb-body');
    // Only restore form if it was replaced with success message
    if (!body.querySelector('#ty-fb-form')) {
      body.innerHTML =
        '<p class="small mb-3 ty-fb-hint">Found a bug? Have a suggestion? We\'d love to hear from you.</p>' +
        '<form id="ty-fb-form" novalidate>' +
          '<input type="text" name="website" style="position:absolute;left:-9999px" tabindex="-1" autocomplete="off">' +
          '<div class="d-flex gap-2 mb-3" role="group" aria-label="Feedback type">' +
            '<input type="radio" class="btn-check" name="fb-type" id="fb-bug"        value="Bug Report"  autocomplete="off">' +
            '<label class="btn btn-sm btn-outline-light" for="fb-bug">Bug</label>' +
            '<input type="radio" class="btn-check" name="fb-type" id="fb-suggestion" value="Suggestion"  autocomplete="off">' +
            '<label class="btn btn-sm btn-outline-light" for="fb-suggestion">Suggestion</label>' +
            '<input type="radio" class="btn-check" name="fb-type" id="fb-other"      value="Other"       autocomplete="off" checked>' +
            '<label class="btn btn-sm btn-outline-light" for="fb-other">Other</label>' +
          '</div>' +
          '<textarea class="form-control ty-input mb-3" id="fb-message" rows="4"' +
            ' placeholder="What\'s on your mind?" maxlength="2000" required></textarea>' +
          '<div class="row g-2">' +
            '<div class="col"><input type="text"  class="form-control ty-input" id="fb-name"  placeholder="Name (optional)"  maxlength="100"></div>' +
            '<div class="col"><input type="email" class="form-control ty-input" id="fb-email" placeholder="Email (optional)" maxlength="200"></div>' +
          '</div>' +
        '</form>';
    }
  });
}());
