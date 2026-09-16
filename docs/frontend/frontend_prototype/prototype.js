document.addEventListener('DOMContentLoaded', () => {
  const toast = document.createElement('div');
  toast.className = 'toast hidden';
  toast.setAttribute('role', 'status');
  document.body.appendChild(toast);

  const notify = (message) => {
    toast.textContent = message;
    toast.classList.remove('hidden');
    window.clearTimeout(window.homeOpsToastTimer);
    window.homeOpsToastTimer = window.setTimeout(() => toast.classList.add('hidden'), 2800);
  };

  document.querySelectorAll('[data-toast]').forEach((button) => {
    button.addEventListener('click', () => notify(button.dataset.toast));
  });

  document.querySelectorAll('[data-toggle]').forEach((button) => {
    button.addEventListener('click', () => {
      const target = document.querySelector(button.dataset.toggle);
      if (!target) return;
      const hidden = target.classList.toggle('hidden');
      button.setAttribute('aria-expanded', String(!hidden));
      notify(hidden ? 'Details collapsed.' : 'Details expanded.');
    });
  });

  document.querySelectorAll('[data-tabs]').forEach((tabGroup) => {
    const tabs = tabGroup.querySelectorAll('[data-tab]');
    const panels = document.querySelectorAll(`[data-tab-panel-group="${tabGroup.dataset.tabs}"] [data-tab-panel]`);
    tabs.forEach((tab) => tab.addEventListener('click', () => {
      tabs.forEach((item) => item.classList.toggle('active', item === tab));
      panels.forEach((panel) => panel.classList.toggle('hidden', panel.dataset.tabPanel !== tab.dataset.tab));
      notify(`${tab.textContent.trim()} view selected.`);
    }));
  });

  const drawer = document.querySelector('[data-drawer]');
  document.querySelectorAll('[data-drawer-toggle]').forEach((button) => button.addEventListener('click', () => {
    if (!drawer) return;
    const open = drawer.classList.toggle('open');
    button.setAttribute('aria-expanded', String(open));
  }));

  document.querySelectorAll('[data-theme-toggle]').forEach((button) => button.addEventListener('click', () => {
    document.documentElement.classList.toggle('contrast-theme');
    notify('Theme preview toggled.');
  }));

  document.querySelectorAll('[data-scenario]').forEach((button) => button.addEventListener('click', () => {
    const target = document.querySelector(button.dataset.scenario);
    if (target) target.textContent = button.dataset.scenarioText || 'Scenario state updated.';
    notify(button.dataset.toast || 'Scenario action completed.');
  }));
});
