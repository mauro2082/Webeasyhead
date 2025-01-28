const slider = document.querySelector('.slider');
const slides = document.querySelectorAll('.slide');
const prevBtn = document.querySelector('.prev-btn');
const nextBtn = document.querySelector('.next-btn');
let currentSlide = 0;

function nextSlide() {
  currentSlide = (currentSlide + 1) % slides.length;
  updateSlider();
}

function prevSlide() {
  currentSlide = (currentSlide - 1 + slides.length) % slides.length; // Handles underflow
  updateSlider();
}

function updateSlider() {
  slider.style.transform = `translateX(-${currentSlide * 100}%)`;
}

prevBtn.addEventListener('click', prevSlide);
nextBtn.addEventListener('click', nextSlide);

// Optional: Disable buttons on edge cases (first/last slide)
// You can uncomment and customize this section

// function handleButtonState() {
//   prevBtn.disabled = currentSlide === 0;
//   nextBtn.disabled = currentSlide === slides.length - 1;
// }

// handleButtonState();
// updateSlider(); // Trigger initial state on page load