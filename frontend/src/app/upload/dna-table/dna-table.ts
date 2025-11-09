import {ChangeDetectionStrategy, Component, inject, OnInit} from '@angular/core';
import {MatTableModule} from '@angular/material/table';
import {MatProgressSpinnerModule} from '@angular/material/progress-spinner';
import {MatInputModule} from '@angular/material/input';
import {MatIconModule} from '@angular/material/icon';
import {MatButtonModule} from '@angular/material/button';
import {FormArray, FormGroup, FormsModule, ReactiveFormsModule} from '@angular/forms';
import {MatButtonToggleModule} from '@angular/material/button-toggle';
import {MatPaginatorModule, PageEvent} from '@angular/material/paginator';
import {MatChipsModule} from '@angular/material/chips';
import {DatePipe} from '@angular/common';
import {DnaTableStore} from './dna-table.store';
import {DnaTableFormService} from './dna-table-form.service';
import {LociUpdate, TableRowData} from './models';
import {DeleteConfirmDialog} from './delete-confirm-dialog/delete-confirm-dialog';
import {MatDialog} from '@angular/material/dialog';
import {MatSelectModule} from '@angular/material/select';
import {MatTooltipModule} from '@angular/material/tooltip';
import {NotificationService} from '../../shared/services/notification.service';
import {ScrollingModule} from '@angular/cdk/scrolling';

@Component({
  selector: 'app-dna-table',
  imports: [
    MatTableModule,
    MatProgressSpinnerModule,
    MatInputModule,
    MatIconModule,
    MatButtonModule,
    ReactiveFormsModule,
    MatButtonToggleModule,
    MatPaginatorModule,
    MatChipsModule,
    DatePipe,
    MatSelectModule,
    MatTooltipModule,
    FormsModule,
    ScrollingModule
  ],
  standalone: true,
  templateUrl: './dna-table.html',
  styleUrl: './dna-table.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DnaTable implements OnInit {
  store = inject(DnaTableStore);
  formService = inject(DnaTableFormService);
  private dialog = inject(MatDialog);
  private notificationService = inject(NotificationService);

  private deletedLoci = new Map<number, number[]>();

  // ✅ Track which row is in "adding" mode
  private addingLocusRowId: number | null = null;
  selectedLocusName: string = '';

  columnsToDisplay = [
    'number', 'name', 'role', 'loci_count', 'related_person', 'file', 'actions'
  ];

  ngOnInit() {
    this.store.loadTableData({ page: 1 });
  }

  getFiles(element: TableRowData): Array<{ id: number; file: string; uploaded_at: string }> {
    return element.files || [];
  }

  toggle(row: TableRowData) {
    const wasExpanded = this.isExpanded(row);

    this.store.toggleExpandedRow(row.personId);

    // ✅ Only create form when expanding
    if (!wasExpanded) {
      this.formService.getRowForm(row); // Creates form on demand
    }
  }

  isExpanded(row: TableRowData): boolean {
    return this.store.isRowExpanded(row.personId);
  }

  onPageChange(event: PageEvent) {
    const page = event.pageIndex + 1;
    const pageSize = event.pageSize;

    this.store.changePage({page, pageSize});
  }

  hasChanges(row: TableRowData): boolean {
    const form = this.formService.getRowForm(row);
    return form.dirty;
  }

  isUpdating(row: TableRowData): boolean {
    return this.store.isRowUpdating(row.personId);
  }

  private collectUpdates(form: FormGroup) {
    let nameUpdate: string | undefined;
    let roleUpdate: string | undefined;
    const lociUpdates: LociUpdate[] = [];

    // Collect name
    const nameControl = form.get('name');
    if (nameControl?.dirty && nameControl?.valid) {
      nameUpdate = nameControl.value;
    }

    // Collect role
    const roleControl = form.get('role');
    if (roleControl?.dirty && roleControl?.valid) {
      roleUpdate = roleControl.value;
    }

    // Collect loci
    const lociArray = form.get('loci') as FormArray;
    for (let i = 0; i < lociArray.length; i++) {
      const locusControl = lociArray.at(i);
      const allelesControl = locusControl.get('alleles');

      if (allelesControl?.dirty && allelesControl?.valid) {
        const locusId = locusControl.get('id')?.value;
        const locusName = locusControl.get('locus_name')?.value;
        const {allele_1, allele_2} = this.formService.parseAlleles(allelesControl.value);

        lociUpdates.push({ id: locusId, locus_name: locusName, allele_1, allele_2 });
      }
    }

    return { nameUpdate, roleUpdate, lociUpdates };
  }

  updateRow(row: TableRowData) {

    if (this.isUpdating(row)) {
      return;
    }

    const form = this.formService.getRowForm(row);
    const deletedLociIds = this.deletedLoci.get(row.personId) || [];

    const { nameUpdate, roleUpdate, lociUpdates } = this.collectUpdates(form);

    if (nameUpdate || roleUpdate || lociUpdates.length > 0 || deletedLociIds.length > 0) {
      this.store.updateRow({ row, nameUpdate, roleUpdate, lociUpdates, deletedLociIds });
      form.markAsPristine();
      this.deletedLoci.delete(row.personId);
    }
  }

  // ✅ Check if row is in adding mode
  isAddingLocus(row: TableRowData): boolean {
    return this.addingLocusRowId === row.personId;
  }

  // ✅ Start adding locus (show select)
  startAddingLocus(row: TableRowData) {
    const availableLoci = this.getAvailableLoci(row);

    if (availableLoci.length === 0) {
      this.notificationService.warning('All loci have been added');
      return;
    }

    this.addingLocusRowId = row.personId;
    this.selectedLocusName = '';
  }

  // ✅ Cancel adding
  cancelAddLocus() {
    this.addingLocusRowId = null;
    this.selectedLocusName = '';
  }

  // ✅ When locus selected from dropdown
  onLocusSelected(row: TableRowData, locusName: string) {
    if (!locusName) return;

    // ✅ Add to form (all validation inside)
    this.formService.addLocus(row, locusName);

    // ✅ Add to store
    this.store.addLocusToRow(row.personId, locusName);

    // ✅ Reset & notify
    this.addingLocusRowId = null;
    this.selectedLocusName = '';
    this.notificationService.success(`Added ${locusName}`);
  }

  // ✅ Remove locus
  removeLocus(row: TableRowData, index: number) {
    // ✅ Get locus ID before removing
    const locusId = row.loci[index]?.id;

    // Remove from form service
    this.formService.removeLocus(row, index);

    // Remove from store
    this.store.removeLocusFromRow(row.personId, index);

    // ✅ Track deletion if it has an ID (exists in DB)
    if (locusId) {
      if (!this.deletedLoci.has(row.personId)) {
        this.deletedLoci.set(row.personId, []);
      }
      this.deletedLoci.get(row.personId)!.push(locusId);
    }

    // ✅ Mark form as dirty to enable Update button
    const form = this.formService.getRowForm(row);
    form.markAsDirty();
  }

  // ✅ Get available loci
  getAvailableLoci(row: TableRowData): string[] {
    const allLoci = [
      'D1S1656', 'D2S441', 'D2S1338', 'D3S1358', 'D5S818',
      'D6S1043', 'D7S820', 'D8S1179', 'D10S1248', 'D12S391',
      'D13S317', 'D16S539', 'D18S51', 'D19S433', 'D21S11',
      'D22S1045', 'CSF1PO', 'FGA', 'TH01', 'TPOX', 'vWA',
      'Penta D', 'Penta E',
    ];

    const existingLoci = row.loci.map(l => l.locus_name);
    return allLoci.filter(name => !existingLoci.includes(name));
  }

  confirmDelete(row: TableRowData) {
    const dialogRef = this.dialog.open(DeleteConfirmDialog, {
      width: '400px',
      data: {
        name: row.name,
        role: row.role,
        lociCount: row.loci_count
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        this.store.deleteRecord(row.personId);
      }
    });
  }

  filterByMultiplePersons(persons: Array<{ id: number; name: string; role: string }>) {
    // Get all person IDs
    const personIds = persons.map(p => p.id);

    // Filter locally to show only these persons
    this.store.filterByMultiplePersonsLocal(personIds, persons[0].role);
  }

  // ✅ LOCAL: Click related person in table (no backend call)
  filterByPerson(personId: number, personRole: string) {
    this.store.filterByPersonLocal(personId, personRole);
  }
}
