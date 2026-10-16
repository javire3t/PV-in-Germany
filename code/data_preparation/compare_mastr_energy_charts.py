"""Reconcile saved MaStR aggregates with the saved Energy-Charts workbook."""
import json
import pandas as pd
from data_preparation.read_workbook import read_data
from project_paths import WORKBOOK, DATA, ENERGY_CHARTS, VALIDATION_RESULTS

OUT=VALIDATION_RESULTS/'mastr_energy_charts'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    records,years=read_data(WORKBOOK,'capacity')
    year=max(years)
    ec=pd.DataFrame([{'AGS':r['id'],'state':r['state'],'district':r['name'],'energy_charts_MWp':r['values'][year]} for r in records])
    assert len(ec)==400 and ec.AGS.nunique()==400
    m=pd.read_csv(DATA/'processed/mastr/pv_by_district_2026.csv',dtype={'AGS':str})
    assert len(m)==1600 and not m.duplicated(['AGS','technology']).any()
    ma=m.groupby('AGS',as_index=False).agg(mastr_MWp=('capacity_MWp','sum'),units=('units','sum'))
    comparison=ec.merge(ma,on='AGS',how='outer',validate='one_to_one',indicator=True)
    assert (comparison['_merge']=='both').all()
    comparison=comparison.drop(columns='_merge')
    comparison['difference_MWp']=comparison.mastr_MWp-comparison.energy_charts_MWp
    comparison['difference_pct']=100*comparison.difference_MWp/comparison.energy_charts_MWp
    comparison['absolute_difference_MWp']=comparison.difference_MWp.abs()
    comparison.sort_values('absolute_difference_MWp',ascending=False).to_csv(OUT/'district_comparison.csv',index=False,encoding='utf-8-sig')
    state=comparison.groupby('state',as_index=False)[['energy_charts_MWp','mastr_MWp','difference_MWp']].sum()
    state['difference_pct']=100*state.difference_MWp/state.energy_charts_MWp
    state.to_csv(OUT/'state_comparison.csv',index=False,encoding='utf-8-sig')
    qa=json.loads((DATA/'processed/mastr/validation.json').read_text())
    metadata=json.loads((ENERGY_CHARTS/'chart_text.json').read_text())
    national=sum(qa['national_capacity_MWp'].values())
    ectotal=float(comparison.energy_charts_MWp.sum())
    mapped=float(comparison.mastr_MWp.sum())
    assert abs(mapped-qa['mapped_capacity_MWp'])<1e-6
    assert abs(national-mapped-qa['unmatched_capacity_MWp'])<1e-6
    assert abs(ectotal-metadata[str(year)]['total'])<1e-6
    summary=dict(year=year,mastr_snapshot=qa['snapshot_date'],energy_charts_source=metadata[str(year)]['source'],
        energy_charts_MWp=ectotal,mastr_national_MWp=national,mastr_mapped_MWp=mapped,
        national_difference_MWp=national-ectotal,national_difference_pct=100*(national/ectotal-1),
        unmatched_MWp=qa['unmatched_capacity_MWp'],districts=len(comparison),
        district_capacity_correlation=comparison.energy_charts_MWp.corr(comparison.mastr_MWp),
        median_district_absolute_difference_pct=comparison.difference_pct.abs().median(),
        districts_within_5_pct=int((comparison.difference_pct.abs()<=5).sum()),
        districts_within_10_pct=int((comparison.difference_pct.abs()<=10).sum()),
        districts_mastr_lower=int((comparison.difference_MWp<0).sum()),
        top_differences=comparison.nlargest(10,'absolute_difference_MWp').to_dict('records'),
        states=state.to_dict('records'))
    (OUT/'comparison.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['states','top_differences']},indent=2))
    print(state.to_string(index=False))
    print(comparison.nlargest(10,'absolute_difference_MWp').to_string(index=False))

if __name__=='__main__':
    main()
