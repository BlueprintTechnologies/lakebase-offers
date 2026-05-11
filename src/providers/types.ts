import fs from 'fs';

export interface ProviderConfig {
  apiKey: string;
  baseURL?: string;
}

export interface ModelInfo {
  id: string;
  description: string;
  contextLength?: number;
  maxTokens?: number;
}

export interface LLMProvider {
  id: string;
  displayName: string;
  configure(config: ProviderConfig): Promise<void>;
  listModels(): Promise<ModelInfo[]>;
  streamChat(messages: any[]): AsyncGenerator<any, any, void>;
}