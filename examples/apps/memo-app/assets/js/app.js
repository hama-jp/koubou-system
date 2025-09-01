/**
 * MemoWall - Visual Sticky Notes App
 * JavaScript Application Logic
 */

class MemoWall {
  constructor() {
    this.memos = this.loadMemos();
    this.currentEditingId = null;
    this.initEventListeners();
    this.renderMemos();
  }

  // Initialize event listeners
  initEventListeners() {
    // Header buttons
    document.querySelector('.add-btn').addEventListener('click', () => this.openModal());
    document.querySelector('input[type="text"]').addEventListener('input', (e) => this.searchMemos(e.target.value));
    
    // Modal events
    document.getElementById('memo-form').addEventListener('submit', (e) => this.saveMemo(e));
    document.querySelector('.cancel-btn').addEventListener('click', () => this.closeModal());
    
    // Click outside modal to close
    document.getElementById('memo-modal').addEventListener('click', (e) => {
      if (e.target === e.currentTarget) this.closeModal();
    });
    
    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') this.closeModal();
      if (e.ctrlKey && e.key === 'n') {
        e.preventDefault();
        this.openModal();
      }
    });
  }

  // Generate unique ID
  generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
  }

  // Load memos from localStorage
  loadMemos() {
    try {
      const stored = localStorage.getItem('memowall-data');
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Error loading memos:', error);
      return [];
    }
  }

  // Save memos to localStorage
  saveMemos() {
    try {
      localStorage.setItem('memowall-data', JSON.stringify(this.memos));
    } catch (error) {
      console.error('Error saving memos:', error);
    }
  }

  // Open modal for creating/editing memo
  openModal(memo = null) {
    const modal = document.getElementById('memo-modal');
    const form = document.getElementById('memo-form');
    const titleInput = document.getElementById('memo-title');
    const contentInput = document.getElementById('memo-content');
    
    if (memo) {
      // Edit mode
      this.currentEditingId = memo.id;
      titleInput.value = memo.title;
      contentInput.value = memo.content;
      document.querySelector(`input[name="color"][value="${memo.color}"]`).checked = true;
      document.querySelector('.modal-content h2').textContent = 'メモ編集';
    } else {
      // Create mode
      this.currentEditingId = null;
      form.reset();
      document.querySelector('input[name="color"][value="yellow"]').checked = true;
      document.querySelector('.modal-content h2').textContent = 'メモ作成';
    }
    
    modal.classList.add('active');
    titleInput.focus();
  }

  // Close modal
  closeModal() {
    const modal = document.getElementById('memo-modal');
    modal.classList.remove('active');
    this.currentEditingId = null;
  }

  // Save memo (create or update)
  saveMemo(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const title = formData.get('title').trim();
    const content = formData.get('content').trim();
    const color = formData.get('color');
    
    if (!title || !content) {
      alert('タイトルと内容を入力してください');
      return;
    }
    
    const now = new Date().toISOString();
    
    if (this.currentEditingId) {
      // Update existing memo
      const memo = this.memos.find(m => m.id === this.currentEditingId);
      if (memo) {
        memo.title = title;
        memo.content = content;
        memo.color = color;
        memo.updatedAt = now;
      }
    } else {
      // Create new memo
      const newMemo = {
        id: this.generateId(),
        title,
        content,
        color,
        createdAt: now,
        updatedAt: now
      };
      this.memos.unshift(newMemo);
    }
    
    this.saveMemos();
    this.renderMemos();
    this.closeModal();
  }

  // Delete memo
  deleteMemo(id) {
    if (confirm('このメモを削除しますか？')) {
      this.memos = this.memos.filter(memo => memo.id !== id);
      this.saveMemos();
      this.renderMemos();
    }
  }

  // Search memos
  searchMemos(query) {
    const container = document.getElementById('memo-container');
    const cards = container.querySelectorAll('.memo-card');
    
    cards.forEach(card => {
      const title = card.querySelector('h3').textContent.toLowerCase();
      const content = card.querySelector('p').textContent.toLowerCase();
      const searchTerm = query.toLowerCase();
      
      if (title.includes(searchTerm) || content.includes(searchTerm)) {
        card.style.display = 'inline-block';
      } else {
        card.style.display = 'none';
      }
    });
  }

  // Render all memos
  renderMemos() {
    const container = document.getElementById('memo-container');
    container.innerHTML = '';
    
    this.memos.forEach(memo => {
      const card = this.createMemoCard(memo);
      container.appendChild(card);
    });
  }

  // Create memo card element
  createMemoCard(memo) {
    const card = document.createElement('article');
    card.className = 'memo-card animate-in';
    card.setAttribute('data-color', memo.color);
    card.setAttribute('data-id', memo.id);
    
    // Truncate content if too long
    const truncatedContent = memo.content.length > 150 
      ? memo.content.substring(0, 150) + '...' 
      : memo.content;
    
    card.innerHTML = `
      <h3>${this.escapeHtml(memo.title)}</h3>
      <p>${this.escapeHtml(truncatedContent)}</p>
      <div class="card-actions">
        <button class="edit-btn" data-id="${memo.id}" aria-label="編集">✏️</button>
        <button class="delete-btn" data-id="${memo.id}" aria-label="削除">🗑️</button>
      </div>
    `;
    
    // Event listeners for card buttons
    card.querySelector('.edit-btn').addEventListener('click', () => this.openModal(memo));
    card.querySelector('.delete-btn').addEventListener('click', () => this.deleteMemo(memo.id));
    
    return card;
  }

  // Escape HTML to prevent XSS
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Load sample data (for demo)
  loadSampleData() {
    if (this.memos.length > 0) return; // Don't load if data exists
    
    const sampleMemos = [
      {
        id: this.generateId(),
        title: '今日のタスク',
        content: '・資料の確認\n・メールの返信\n・プロジェクトの進捗確認',
        color: 'yellow',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      },
      {
        id: this.generateId(),
        title: '買い物リスト',
        content: '牛乳、パン、卵、野菜、調味料',
        color: 'pink',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      },
      {
        id: this.generateId(),
        title: 'アイデア',
        content: '新しいアプリの機能について考える。ユーザビリティの向上が必要。',
        color: 'blue',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }
    ];
    
    this.memos = sampleMemos;
    this.saveMemos();
    this.renderMemos();
  }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  window.memoWall = new MemoWall();
  
  // Load sample data on first visit
  if (localStorage.getItem('memowall-first-visit') === null) {
    window.memoWall.loadSampleData();
    localStorage.setItem('memowall-first-visit', 'false');
  }
});

// Export for testing (if needed)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = MemoWall;
}