import {
  ApplicationConfig,
  isDevMode,
  provideBrowserGlobalErrorListeners,
  provideZonelessChangeDetection
} from '@angular/core';
import {provideRouter} from '@angular/router';
import {routes} from './app.routes';
import {provideHttpClient} from '@angular/common/http';
import {ENVIRONMENT} from './config/environment.config';
import {devEnvironment} from './config/environment.development';
import {prodEnvironment} from './config/environment.production';

const currentEnvironment = isDevMode() ? devEnvironment : prodEnvironment;

export const appConfig: ApplicationConfig = {
  providers: [
    {provide: ENVIRONMENT, useValue: currentEnvironment},
    provideBrowserGlobalErrorListeners(),
    provideZonelessChangeDetection(),
    provideRouter(routes),
    provideHttpClient(),
  ]
};
