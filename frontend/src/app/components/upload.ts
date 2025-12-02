import {ChangeDetectionStrategy, Component} from '@angular/core';
import {MatButtonModule} from '@angular/material/button';
import {MatIconModule} from '@angular/material/icon';
import {MatButtonToggleModule} from '@angular/material/button-toggle';
import {DnaTable} from './dna-table/dna-table';


@Component({
  selector: 'app-components',
  standalone: true,
  imports: [
    MatButtonModule, MatIconModule, MatButtonToggleModule, DnaTable
  ],
  templateUrl: './upload.html',
  styleUrl: './upload.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Upload {

}
