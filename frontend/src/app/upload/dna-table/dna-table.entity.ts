import {entityConfig} from '@ngrx/signals/entities';
import {type} from '@ngrx/signals';
import {DnaRecord} from '../models';

export const dnaEntityConfig = entityConfig({
  entity: type<DnaRecord>(),
  collection: 'dnaRecords',
  selectId: (record) => record.id
})
