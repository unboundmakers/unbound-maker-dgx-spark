// The external preview is sandboxed, with network and community publishing disabled.
document.querySelectorAll('.community').forEach((element) => { element.hidden = true; });
const note = document.createElement('p');
note.textContent = '概念选项预览。右侧仅支持导入机身颜色；其他选项尚未接入 Isaac Sim。';
document.body.prepend(note);
window.addEventListener('message', (event) => {
  if (event.source !== window.parent || event.data?.type !== 'unbound:request-color') return;
  const color = document.getElementById('body')?.getAttribute('fill');
  if (/^#[0-9a-f]{6}$/i.test(color || '')) {
    window.parent.postMessage({type: 'unbound:concept-color', color}, '*');
  }
});
