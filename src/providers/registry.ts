import { LLMProvider } from './types';
import { OmniRouteProviderInstance } from './omniroute';

export class ProviderRegistry {
  private static instance;
  private providers = new Map<string, LLMProvider>();

  private constructor() {
    this.register(OmniRouteProviderInstance);
  }

  static getInstance() {
    if (!ProviderRegistry.instance) {
      ProviderRegistry.instance = new ProviderRegistry();
    }
    return ProviderRegistry.instance;
  }

  register(provider: LLMProvider) {
    this.providers.set(provider.id, provider);
  }

  getProvider(id: string): LLMProvider | undefined {
    return this.providers.get(id);
  }

  getProviders(): LLMProvider[] {
    return Array.from(this.providers.values());
  }
}

export const providerRegistry = ProviderRegistry.getInstance();