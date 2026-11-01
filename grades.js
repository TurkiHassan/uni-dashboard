/* Published Blackboard grades. All values originate in the validated sync payload. */
(() => {
  'use strict';
  const el = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const courseKey = item => item.courseId || item.code || item.course || '';
  const hasGrade = item => String(item.grade ?? '').trim() !== '';
  const formatTime = value => {
    if (!value || Number.isNaN(new Date(value).getTime())) return 'لم يكتمل فحص التقديرات بعد';
    return new Intl.DateTimeFormat('ar-SA-u-ca-gregory', {dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Riyadh'}).format(new Date(value));
  };
  function render() {
    const state = window.DATA?.grades || {};
    const items = Array.isArray(state.items) ? state.items : [];
    const picker = el('gradeCourse');
    const selected = picker.value;
    const courses = new Map(Object.entries(state.courses || {}).map(([id,course]) => [id,course.name]));
    for (const item of items) courses.set(courseKey(item), item.course);
    picker.innerHTML = '<option value="">كل المقررات</option>' + [...courses].map(([key,name]) => `<option value="${escape(key)}">${escape(name)}</option>`).join('');
    if (courses.has(selected)) picker.value = selected;
    const filter = el('gradeFilter').value;
    const changed = new Set((state.changes || []).map(change => change.id));
    const rows = items.filter(item => (!picker.value || picker.value === courseKey(item)) &&
      (filter === 'all' || (filter === 'graded' && hasGrade(item)) || (filter === 'pending' && !hasGrade(item)) || (filter === 'changed' && changed.has(item.id))));
    el('gradeCount').textContent = `${rows.length} بند · ${items.filter(hasGrade).length} تقدير مرصود من ${items.length}`;
    const health = el('gradesHealth');
    const age = state.lastSuccessAt ? (Date.now() - new Date(state.lastSuccessAt).getTime()) / 36e5 : Infinity;
    health.dataset.state = ['ERROR','LOGIN_REQUIRED'].includes(state.status) ? 'error' : state.status === 'PARTIAL' || age > 72 ? 'warn' : 'ok';
    el('gradeSyncState').textContent = state.status === 'LOGIN_REQUIRED' ? 'تحتاج جلسة Blackboard إلى تسجيل دخول' : state.status === 'PARTIAL' ? 'اكتمل بعض المقررات؛ البقية تعرض آخر بيانات محفوظة' : state.status === 'ERROR' ? 'تعذر آخر فحص؛ هذه آخر بيانات محفوظة' : age > 72 ? 'التقديرات تحتاج إلى تحقق جديد' : 'تم التحقق من التقديرات';
    el('gradeSyncTime').textContent = `آخر فحص مكتمل: ${formatTime(state.lastSuccessAt)}`;
    if (state.lastSuccessAt) el('gradeSyncTime').dateTime = state.lastSuccessAt;
    const statuses = {'graded':'رُصدت','submitted':'سُلّمت','not graded':'لم تُرصد','not submitted':'لم تُسلّم','missing':'غير مُسلّم','ongoing':'مستمر','closed':'مغلق'};
    el('gradeRows').innerHTML = rows.map(item => {
      const courseState = state.courses?.[item.courseId];
      const stale = courseState && courseState.status !== 'OK';
      return `<tr><td class="grades-item">${escape(item.item)}${changed.has(item.id)?'<span class="grades-change">تقدير جديد أو معدّل</span>':''}</td><td class="grades-course">${escape(item.course)}${stale?'<br><span class="grades-muted">آخر بيانات محفوظة</span>':''}</td><td><span class="grades-value" dir="ltr">${hasGrade(item)?escape(item.grade):'<span class="grades-muted" dir="rtl">لم تُرصد</span>'}</span></td><td>${escape(statuses[String(item.status || '').toLowerCase()] || item.status || '—')}</td></tr>`;
    }).join('');
    el('gradeTable').hidden = rows.length === 0;
    el('gradesEmpty').hidden = rows.length > 0;
    el('gradesEmpty').textContent = items.length ? 'لا توجد تقديرات تطابق هذا التصفية.' : 'ستظهر التقديرات هنا بعد اكتمال المراجعة التلقائية التالية لبلاك بورد.';
  }
  async function refresh() {
    const button = el('gradeRefresh');
    button.disabled = true;
    button.textContent = 'جارٍ جلب آخر تحديث…';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(`data.js?refresh=${Date.now()}`, {cache:'no-store',signal:controller.signal});
      if (!response.ok) throw new Error('Fetch failed');
      const match = (await response.text()).match(/^\s*window\.DATA\s*=\s*([\s\S]*?)\s*;?\s*$/);
      if (!match) throw new Error('Invalid data');
      const next = JSON.parse(match[1]);
      if (!Array.isArray(next.courses) || !Array.isArray(next.tasks)) throw new Error('Invalid payload');
      Object.assign(window.DATA, next);
      window.dispatchEvent(new CustomEvent('dashboard:data'));
      el('gradeRefreshMessage').textContent = 'تم جلب آخر نسخة منشورة من اللوحة.';
    } catch (_) {
      el('gradeRefreshMessage').textContent = 'تعذر جلب التحديث. ما زالت آخر بيانات محفوظة معروضة؛ أعد المحاولة عند الاتصال.';
    } finally {
      clearTimeout(timeout);
      button.disabled = false;
      button.textContent = 'جلب آخر تحديث';
    }
  }
  el('gradeCourse').addEventListener('change', render);
  el('gradeFilter').addEventListener('change', render);
  el('gradeRefresh').addEventListener('click', refresh);
  window.addEventListener('dashboard:data', render);
  render();
})();
