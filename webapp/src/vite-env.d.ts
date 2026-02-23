/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MIDDLEWARE_HOST: string
  readonly VITE_MIDDLEWARE_API_KEY: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
