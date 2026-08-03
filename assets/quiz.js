/**
 * Shared quiz widget — include once per lesson page.
 * Usage: <div class="quiz" data-correct="2"> ... <div class="quiz-feedback"></div></div>
 *
 * Each .quiz-options button gets an index (0-based).
 * data-correct = index of the correct answer.
 */
document.querySelectorAll('.quiz').forEach(quiz => {
  const correct = parseInt(quiz.dataset.correct, 10);
  const buttons = quiz.querySelectorAll('.quiz-options button');
  const feedback = quiz.querySelector('.quiz-feedback');

  buttons.forEach((btn, i) => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.disabled = true);
      if (i === correct) {
        btn.classList.add('correct');
        feedback.textContent = '正確！' + (btn.dataset.explain || '');
        feedback.className = 'quiz-feedback correct';
      } else {
        btn.classList.add('wrong');
        buttons[correct].classList.add('correct');
        feedback.textContent = '不對。' + (btn.dataset.explain || '');
        feedback.className = 'quiz-feedback wrong';
      }
    });
  });
});
