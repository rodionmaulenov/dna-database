import {ChangeDetectionStrategy, Component} from '@angular/core';
import {RouterOutlet} from '@angular/router';
import {Upload} from './components/upload';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, Upload],
  templateUrl: './app.html',
  styleUrl: './app.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class App {

}
