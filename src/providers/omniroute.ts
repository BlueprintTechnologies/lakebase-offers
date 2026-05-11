export class OmniRouteProvider {
  public readonly id = 'omnirouter';
  public readonly displayName = 'OmniRoute';
  private config: any;

  constructor() {
    const userConfigPath = process.env.HOME + '/.config/open-pilot/config.json';
    const workspaceConfigPath = process.cwd() + '/.open-pilot/config.json';

    const userConfig = fs.existsSync(userConfigPath) ? JSON.parse(fs.readFileSync(userConfigPath, 'utf8')) : {};
    const workspaceConfig = fs.existsSync(workspaceConfigPath) ? JSON.parse(fs.readFileSync(workspaceConfigPath, 'utf8')) : {};

    // Workspace config overrides user config
    this.config = { ...userConfig, ...workspaceConfig };
  }

  configure(config: any): Promise<void> {
    // Config already loaded in constructor; no-op
    return Promise.resolve();
  }

  async listModels() {
    // Return placeholder models
    return [
      { id: 'gpt-3.5-turbo', description: 'GPT-3.5 Turbo', contextLength: 16384, maxTokens: 4096 },
      { id: 'gpt-4', description: 'GPT-4', contextLength: 32768, maxTokens: 8192 },
    ];
  }

  async* streamChat(messages: any[]): AsyncGenerator<any, any, void> {
    yield { role: 'assistant', content: 'Hello! This is a placeholder response.' };
  }
}

export const OmniRouteProviderInstance = new OmniRouteProvider();