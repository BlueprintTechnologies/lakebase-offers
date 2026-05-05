document$.subscribe(() => {
  mermaid.initialize({ startOnLoad: false, theme: "default" });
  mermaid.run({ querySelector: "code.language-mermaid" });
});
