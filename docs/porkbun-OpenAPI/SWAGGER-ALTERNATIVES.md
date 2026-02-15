# Swagger Alternatives (Local macOS)

This is a shortlist of OpenAPI documentation viewers that are cleaner than default Swagger UI and work well locally on macOS.

## Quick recommendation

If you want the fastest path with minimal setup:

1. **Redoc CE (via Redocly CLI)** for quick local preview + static HTML export.
2. **Scalar API Reference** if you want the most modern UI feel.

## 1) Redoc CE / Redocly CLI

Best for: stable, polished docs and easy local preview/build.

### Local preview
```bash
npx @redocly/cli preview-docs /Users/philip/Documents/New\ project/porkbun-openapi.yaml
```

### Build static HTML
```bash
npx @redocly/cli build-docs /Users/philip/Documents/New\ project/porkbun-openapi.yaml -o /Users/philip/Documents/New\ project/porkbun-redoc.html
```

Sources:
- [Redocly CLI `preview-docs`](https://redocly.com/docs/cli/v1/commands/preview-docs)
- [Redocly CLI `build-docs`](https://redocly.com/docs/cli/commands/build-docs)

## 2) Scalar API Reference

Best for: modern, clean docs UI and nice reader experience.

### Minimal local setup
Create `scalar.html`:

```html
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Scalar API Reference</title>
  </head>
  <body>
    <div id="app"></div>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
    <script>
      Scalar.createApiReference('#app', {
        url: '/porkbun-openapi.json'
      })
    </script>
  </body>
</html>
```

Serve locally from project folder:
```bash
cd /Users/philip/Documents/New\ project
python3 -m http.server 8080
```
Open: `http://localhost:8080/scalar.html`

Sources:
- [Scalar Getting Started](https://scalar.com/products/api-references/getting-started)
- [Scalar Configuration](https://guides.scalar.com/scalar/scalar-api-references/configuration)
- [Scalar OpenAPI support](https://scalar.com/products/api-references/openapi)

## 3) Stoplight Elements

Best for: embedding API docs into an existing portal/app (React or web components).

### Minimal HTML embed
```html
<script src="https://unpkg.com/@stoplight/elements/web-components.min.js"></script>
<link rel="stylesheet" href="https://unpkg.com/@stoplight/elements/styles.min.css">
<elements-api apiDescriptionUrl="/porkbun-openapi.json" router="hash" layout="sidebar" />
```

Source:
- [Stoplight Elements (official)](https://stoplight.io/open-source/elements)
- [Stoplight Elements GitHub](https://github.com/stoplightio/elements)

## 4) RapiDoc

Best for: lightweight single-file embed with strong “try it” ergonomics.

### Minimal HTML embed
```html
<script type="module" src="https://unpkg.com/rapidoc/dist/rapidoc-min.js"></script>
<rapi-doc spec-url="/porkbun-openapi.json"></rapi-doc>
```

Source:
- [RapiDoc GitHub](https://github.com/rapi-doc/RapiDoc)

## Notes on cloud-hosted options

Tools like Bump.sh are good, but their preview flow is primarily cloud-hosted. If your goal is strictly local-first, Redoc/Scalar/Elements/RapiDoc are usually better fits.

Source:
- [Bump CLI preview](https://docs.bump.sh/help/continuous-integration/cli/)

## Suggested next step for your Porkbun spec

Try both locally and pick the one you like visually:

1. `Redocly preview-docs` for immediate no-code viewing.
2. `Scalar` HTML for a modern alternative.

Your spec files are ready to use:
- `/Users/philip/Documents/New project/porkbun-openapi.yaml`
- `/Users/philip/Documents/New project/porkbun-openapi.json`
