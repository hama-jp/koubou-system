/**
 * 日めくりカレンダー
 *  - 今日の日付を日本語表記で表示
 *  - 曜日を色分け（土曜青、日曜赤、平日黒）
 *  - 祝日を赤で表示（簡易リスト）
 *  - 六曜を表示
 *  - グラスモーフィズムデザイン
 *  - アニメーション（フェードイン/アウト、ホバー）
 *  - レスポンシブ対応
 *  - ダークモード自動検出
 */

(function () {
  const monthYearEl = document.getElementById('month-year');
  const dateNumberEl = document.getElementById('date-number');
  const weekdayEl = document.getElementById('weekday');
  const sixyoEl = document.getElementById('sixyo');

  const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
  const sixyoList = ['大安', '仏滅', '赤口', '先勝', '友引', '先負'];

  // 祝日リスト（2025年例）
  const holidays = [
    { date: '2025-01-01', name: '元日' },
    { date: '2025-01-08', name: '成人の日' },
    { date: '2025-02-11', name: '建国記念の日' },
    { date: '2025-02-23', name: '天皇誕生日' },
    { date: '2025-03-20', name: '春分の日' },
    { date: '2025-04-29', name: '昭和の日' },
    { date: '2025-05-03', name: '憲法記念日' },
    { date: '2025-05-04', name: 'みどりの日' },
    { date: '2025-05-05', name: 'こどもの日' },
    { date: '2025-07-21', name: '海の日' },
    { date: '2025-08-11', name: '山の日' },
    { date: '2025-09-18', name: '敬老の日' },
    { date: '2025-09-23', name: '秋分の日' },
    { date: '2025-10-09', name: '体育の日' },
    { date: '2025-11-03', name: '文化の日' },
    { date: '2025-11-23', name: '勤労感謝の日' },
    { date: '2025-12-23', name: '天皇誕生日' }
  ];

  function formatDate(date) {
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    return `${year}年${month}月${day}日`;
  }

  function getWeekday(date) {
    return weekdays[date.getDay()];
  }

  function isHoliday(date) {
    const key = date.toISOString().slice(0, 10);
    return holidays.find(h => h.date === key);
  }

  function getSixyo(date) {
    const reference = new Date('2023-01-01'); // 大安
    const diff = Math.floor((date - reference) / (1000 * 60 * 60 * 24));
    const idx = ((diff % 6) + 6) % 6; // 正の余り
    return sixyoList[idx];
  }

  function updateCalendar() {
    const today = new Date();
    const formatted = formatDate(today);
    const weekday = getWeekday(today);
    const holiday = isHoliday(today);
    const sixyo = getSixyo(today);

    // アニメーション: フェードアウト→更新→フェードイン
    dateNumberEl.style.opacity = 0;
    setTimeout(() => {
      monthYearEl.textContent = `${today.getFullYear()}年${today.getMonth() + 1}月`;
      dateNumberEl.textContent = formatted;
      weekdayEl.textContent = weekday;
      sixyoEl.textContent = sixyo;

      // 曜日色分け
      weekdayEl.classList.remove('sat', 'sun', 'holiday');
      if (holiday) weekdayEl.classList.add('holiday');
      else if (today.getDay() === 6) weekdayEl.classList.add('sat');
      else if (today.getDay() === 0) weekdayEl.classList.add('sun');

      dateNumberEl.style.opacity = 1;
    }, 300);
  }

  // 初期表示
  updateCalendar();

  // 毎日0時に更新（ブラウザが開いている限り）
  const now = new Date();
  const msUntilMidnight =
    new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1) - now;
  setTimeout(function () {
    updateCalendar();
    setInterval(updateCalendar, 24 * 60 * 60 * 1000);
  }, msUntilMidnight);
})();