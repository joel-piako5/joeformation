// quiz.js - validation, progression, sauvegarde locale, confirmation avant envoi
document.addEventListener('DOMContentLoaded', function () {
  const form = document.querySelector('form');
  if (!form) return;

  const questions = Array.from(document.querySelectorAll('div.mb-3.p-3.border.rounded'));
  const total = questions.length;
  // create progress UI
  const progressWrap = document.createElement('div');
  progressWrap.className = 'progress-wrap';
  progressWrap.innerHTML = `
    <div class="progress-text">Progression : <span id="progress-count">0</span> / ${total}</div>
    <div class="progress">
      <div id="progress-bar" class="progress-bar" role="progressbar" style="width:0%" aria-valuemin="0" aria-valuemax="100"></div>
    </div>`;
  form.parentNode.insertBefore(progressWrap, form);

  const progressCount = document.getElementById('progress-count');
  const progressBar = document.getElementById('progress-bar');

  // load saved answers if exist
  const STORAGE_KEY = 'quiz_answers_v1';
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); } catch(e){ saved = {}; }

  // attach listeners to each question radios
  questions.forEach((qDiv, idx) => {
    const radios = qDiv.querySelectorAll('input[type="radio"]');
    radios.forEach(radio => {
      // restore checked from localStorage
      const qname = radio.name;
      if (saved[qname] && saved[qname] === radio.value) {
        radio.checked = true;
      }
      radio.addEventListener('change', () => {
        // save to localStorage
        saved[radio.name] = radio.value;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
        updateProgress();
      });
    });
  });

  // update progress UI
  function updateProgress(){
    const answered = questions.reduce((acc, qDiv) => {
      return acc + (qDiv.querySelector('input[type="radio"]:checked') ? 1 : 0);
    }, 0);
    progressCount.innerText = answered;
    const pct = Math.round((answered / total) * 100);
    progressBar.style.width = pct + '%';
    progressBar.setAttribute('aria-valuenow', pct);
  }

  updateProgress();

  // on submit: ensure all questions answered, confirm
  form.addEventListener('submit', function(e) {
    const unanswered = questions.filter(qDiv => !qDiv.querySelector('input[type="radio"]:checked'));
    if (unanswered.length > 0) {
      e.preventDefault();
      // scroll to first unanswered
      const first = unanswered[0];
      first.scrollIntoView({behavior: 'smooth', block: 'center'});
      // highlight briefly
      first.style.boxShadow = '0 0 0 3px rgba(255,204,0,0.25)';
      setTimeout(()=> first.style.boxShadow = '', 2000);
      alert(Il reste ${unanswered.length} question(s) sans réponse. Merci de répondre à toutes avant de soumettre.);
      return false;
    }

    // confirmation
    const ok = confirm('Voulez-vous vraiment soumettre vos réponses ? Vous ne pourrez plus les modifier.');
    if (!ok) {
      e.preventDefault();
      return false;
    }

    // Optionnel : clear saved answers after submit (décommente si souhaité)
    // localStorage.removeItem(STORAGE_KEY);
  });

  // small UX: clicking label checks radio (Bootstrap already does) and update progress automatically handled via change events

});