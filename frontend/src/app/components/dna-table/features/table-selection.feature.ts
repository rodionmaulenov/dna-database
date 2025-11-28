import {signalStoreFeature, withMethods} from '@ngrx/signals';
import {TableRowData} from '../models';
import {Signal} from '@angular/core';
import {MatTableDataSource} from '@angular/material/table';
import {SelectionModel} from '@angular/cdk/collections';


export function WithTableSelection(
  dataSource: Signal<MatTableDataSource<TableRowData>>,
  selection: SelectionModel<TableRowData>
) {
  return signalStoreFeature(

    withMethods(() => ({

      isAllSelected() {
        const numSelected = selection.selected.length;
        const numRows = dataSource().data.length;
        return numSelected === numRows;
      },

      toggleAllRows() {
        if (this.isAllSelected()) {
          selection.clear();
          return;
        }

        selection.select(...dataSource().data);
      },

      checkboxLabel(row?: TableRowData): string {
        if (!row) {
          return `${this.isAllSelected() ? 'deselect' : 'select'} all`;
        }
        return `${selection.isSelected(row) ? 'deselect' : 'select'} row ${row.id + 1}`;
      },

      clearSelection() {
        selection.clear();
      }

    })),
  );
}
