/* ==============================
   StickyBoard – JavaScript
   ============================== */

(() => {
  'use strict';

  /* ---------- Config ---------- */
  const STORAGE_KEY = 'stickyBoard';
  let selectedColor = '#FFEB3B';
  let noteIdCounter = 0;

  /* ---------- Initialize ---------- */
  document.addEventListener('DOMContentLoaded', () => {
    const board = document.getElementById('board');
    const addButton = document.getElementById('add-sticky');
    const colorButtons = document.querySelectorAll('.color-btn');

    if (!board || !addButton) {
      console.error('Required elements not found');
      return;
    }

    // Load saved notes
    loadNotes();

    // Add button click handler
    addButton.addEventListener('click', () => {
      const note = createStickyNote();
      board.appendChild(note);
      saveNotes();
    });

    // Color picker handlers
    colorButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        selectedColor = btn.dataset.color;
        // Visual feedback
        colorButtons.forEach(b => b.style.border = '2px solid transparent');
        btn.style.border = '2px solid rgba(0,0,0,0.3)';
      });
    });

    // Board click to add note
    board.addEventListener('click', (e) => {
      if (e.target === board) {
        const rect = board.getBoundingClientRect();
        const note = createStickyNote(
          e.clientX - rect.left - 100,
          e.clientY - rect.top - 75
        );
        board.appendChild(note);
        saveNotes();
      }
    });
  });

  /* ---------- Create Sticky Note ---------- */
  function createStickyNote(x = 100, y = 100, data = {}) {
    const note = document.createElement('div');
    note.className = 'sticky-note';
    note.id = data.id || `note-${++noteIdCounter}`;
    note.style.left = `${x}px`;
    note.style.top = `${y}px`;
    note.style.backgroundColor = data.color || selectedColor;

    // Apply color class for styling
    const colorClass = getColorClass(data.color || selectedColor);
    if (colorClass) note.classList.add(colorClass);

    // Header with close button
    const header = document.createElement('div');
    header.className = 'note-header';
    
    const closeBtn = document.createElement('button');
    closeBtn.className = 'note-close';
    closeBtn.innerHTML = '×';
    closeBtn.onclick = () => {
      note.classList.add('removing');
      setTimeout(() => {
        note.remove();
        saveNotes();
      }, 200);
    };
    header.appendChild(closeBtn);

    // Content area
    const content = document.createElement('div');
    content.className = 'note-content';
    content.contentEditable = true;
    content.textContent = data.content || 'クリックして編集';
    
    // Save on content change
    content.addEventListener('blur', saveNotes);
    content.addEventListener('input', debounce(saveNotes, 500));

    // Assemble note
    note.appendChild(header);
    note.appendChild(content);

    // Make draggable
    makeDraggable(note);

    return note;
  }

  /* ---------- Make Draggable ---------- */
  function makeDraggable(element) {
    let isDragging = false;
    let currentX;
    let currentY;
    let initialX;
    let initialY;

    element.addEventListener('mousedown', dragStart);

    function dragStart(e) {
      if (e.target.classList.contains('note-content') || 
          e.target.classList.contains('note-close')) {
        return;
      }

      initialX = e.clientX - element.offsetLeft;
      initialY = e.clientY - element.offsetTop;

      isDragging = true;
      element.classList.add('dragging');

      document.addEventListener('mousemove', drag);
      document.addEventListener('mouseup', dragEnd);
    }

    function drag(e) {
      if (!isDragging) return;

      e.preventDefault();
      currentX = e.clientX - initialX;
      currentY = e.clientY - initialY;

      element.style.left = `${currentX}px`;
      element.style.top = `${currentY}px`;
    }

    function dragEnd() {
      isDragging = false;
      element.classList.remove('dragging');
      document.removeEventListener('mousemove', drag);
      document.removeEventListener('mouseup', dragEnd);
      saveNotes();
    }
  }

  /* ---------- Save/Load Functions ---------- */
  function saveNotes() {
    const board = document.getElementById('board');
    const notes = Array.from(board.querySelectorAll('.sticky-note')).map(note => ({
      id: note.id,
      content: note.querySelector('.note-content').textContent,
      color: note.style.backgroundColor,
      left: parseInt(note.style.left),
      top: parseInt(note.style.top)
    }));
    
    localStorage.setItem(STORAGE_KEY, JSON.stringify(notes));
  }

  function loadNotes() {
    const board = document.getElementById('board');
    const saved = localStorage.getItem(STORAGE_KEY);
    
    if (!saved) return;

    try {
      const notes = JSON.parse(saved);
      notes.forEach(noteData => {
        const note = createStickyNote(noteData.left, noteData.top, noteData);
        board.appendChild(note);
      });
    } catch (e) {
      console.error('Failed to load notes:', e);
    }
  }

  /* ---------- Utility Functions ---------- */
  function getColorClass(color) {
    const colorMap = {
      '#FFEB3B': 'yellow',
      '#E91E63': 'pink',
      '#2196F3': 'blue',
      '#4CAF50': 'green',
      '#FF9800': 'orange'
    };
    return colorMap[color] || '';
  }

  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }
})();