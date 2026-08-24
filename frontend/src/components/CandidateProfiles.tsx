import {ChangeEvent, FormEvent, ReactNode, useEffect, useState} from 'react';
import {
  BriefcaseBusiness,
  ExternalLink,
  FileUp,
  GraduationCap,
  LoaderCircle,
  Pencil,
  Plus,
  Save,
  Trash2,
  UserRound,
  X,
} from 'lucide-react';
import {
  ApiError,
  CandidateProfile,
  CandidateProfileInput,
  CandidateSummary,
  createCandidateProfile,
  deleteCandidateProfile,
  getCandidateProfile,
  importResumePreview,
  listCandidates,
  updateCandidateProfile,
} from '../lib/api';

const IS_EXTERNAL_PREVIEW = import.meta.env.VITE_PREVIEW_MODE === 'true';

interface CandidateProfilesProps {
  selectedCandidateId: string;
  onSelectionChange: (candidateId: string) => void;
}

interface ProfileFormState {
  fullName: string;
  email: string;
  phone: string;
  location: string;
  linkedinUrl: string;
  githubUrl: string;
  portfolioUrl: string;
  headline: string;
  summary: string;
  skills: {name: string; category: string}[];
  certifications: {name: string; organization: string; year: string}[];
  projects: {name: string; description: string; technologies: string}[];
  experiences: {
    jobTitle: string;
    company: string;
    startDate: string;
    endDate: string;
    description: string;
  }[];
  education: {degree: string; institution: string; year: string}[];
}

type FieldErrors = Record<string, string>;

const EMPTY_FORM: ProfileFormState = {
  fullName: '',
  email: '',
  phone: '',
  location: '',
  linkedinUrl: '',
  githubUrl: '',
  portfolioUrl: '',
  headline: '',
  summary: '',
  skills: [],
  certifications: [],
  projects: [],
  experiences: [],
  education: [],
};

export function CandidateProfiles({
  selectedCandidateId,
  onSelectionChange,
}: CandidateProfilesProps) {
  const [candidates, setCandidates] = useState<CandidateSummary[]>([]);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [form, setForm] = useState<ProfileFormState>(EMPTY_FORM);
  const [mode, setMode] = useState<'view' | 'create' | 'edit'>('view');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [importWarnings, setImportWarnings] = useState<string[]>([]);

  useEffect(() => {
    let active = true;
    async function loadCandidateList() {
      setIsLoading(true);
      try {
        const items = await listCandidates();
        if (!active) return;
        setCandidates(items);
        const selectedExists = items.some((item) => item.id === selectedCandidateId);
        onSelectionChange(selectedExists ? selectedCandidateId : items[0]?.id || '');
      } catch (error) {
        if (active) setErrorMessage(getErrorMessage(error, 'Candidate profiles could not be loaded.'));
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void loadCandidateList();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    async function loadProfile() {
      if (!selectedCandidateId) {
        setProfile(null);
        return;
      }
      setIsLoading(true);
      setErrorMessage('');
      try {
        const selected = await getCandidateProfile(selectedCandidateId);
        if (active) setProfile(selected);
      } catch (error) {
        if (active) setErrorMessage(getErrorMessage(error, 'Candidate profile could not be loaded.'));
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void loadProfile();
    return () => {
      active = false;
    };
  }, [selectedCandidateId]);

  function beginCreate() {
    setForm(cloneEmptyForm());
    setMode('create');
    setErrorMessage('');
    setSuccessMessage('');
    setFieldErrors({});
    setImportWarnings([]);
  }

  function beginEdit() {
    if (!profile) return;
    setForm(profileToForm(profile));
    setMode('edit');
    setErrorMessage('');
    setSuccessMessage('');
    setFieldErrors({});
    setImportWarnings([]);
  }

  async function handleResumeImport(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setIsImporting(true);
    setErrorMessage('');
    setSuccessMessage('');
    setFieldErrors({});
    try {
      const preview = await importResumePreview(file);
      setForm(profileInputToForm(preview.profile));
      setMode('create');
      setImportWarnings(preview.warnings);
      setSuccessMessage(`Imported ${preview.file_name}. Review every field before saving.`);
    } catch (error) {
      setErrorMessage(getErrorMessage(error, 'The resume could not be imported.'));
    } finally {
      setIsImporting(false);
    }
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationErrors = validateProfileForm(form);
    if (Object.keys(validationErrors).length) {
      setFieldErrors(validationErrors);
      setErrorMessage('Correct the highlighted profile fields before saving.');
      return;
    }
    setIsSaving(true);
    setErrorMessage('');
    setSuccessMessage('');
    setFieldErrors({});
    try {
      const payload = formToPayload(form);
      const saved = mode === 'edit' && profile
        ? await updateCandidateProfile(profile.id, payload)
        : await createCandidateProfile(payload);
      const items = await listCandidates();
      setCandidates(items);
      setProfile(saved);
      onSelectionChange(saved.id);
      setMode('view');
      setImportWarnings([]);
      setSuccessMessage(mode === 'create' ? 'Profile created successfully.' : 'Profile saved successfully.');
    } catch (error) {
      setErrorMessage(getErrorMessage(error, 'The candidate profile could not be saved.'));
      setFieldErrors(getApiFieldErrors(error));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete() {
    if (!profile || !window.confirm(`Delete ${profile.full_name}'s profile? This cannot be undone.`)) {
      return;
    }
    setIsSaving(true);
    setErrorMessage('');
    setSuccessMessage('');
    try {
      await deleteCandidateProfile(profile.id);
      const items = await listCandidates();
      setCandidates(items);
      const nextId = items[0]?.id || '';
      setProfile(null);
      onSelectionChange(nextId);
      setMode(nextId ? 'view' : 'create');
      if (!nextId) setForm(cloneEmptyForm());
    } catch (error) {
      setErrorMessage(getErrorMessage(error, 'The candidate profile could not be deleted.'));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="mt-8 border-y border-border/45 py-6">
      <div className="flex flex-wrap items-end gap-3">
        <label htmlFor="candidate-profile" className="min-w-0 flex-1">
          <span id="candidate-profile-label" className="cozy-label mb-2 block">
            Candidate profile
          </span>
          <div className="cozy-field flex items-center rounded-lg px-4 transition">
            <UserRound className="mr-3 size-4 shrink-0 text-brand-amber" />
            <select
              id="candidate-profile"
              aria-labelledby="candidate-profile-label"
              value={selectedCandidateId}
              disabled={isLoading || mode !== 'view' || !candidates.length}
              onChange={(event) => onSelectionChange(event.target.value)}
              className="min-w-0 flex-1 bg-transparent py-3 text-sm text-foreground outline-none disabled:opacity-70"
            >
              {!candidates.length && <option value="">No profiles yet</option>}
              {candidates.map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.full_name} · {candidate.email ?? 'Candidate profile'}
                </option>
              ))}
            </select>
          </div>
        </label>
        {IS_EXTERNAL_PREVIEW ? (
          <button
            className="cozy-button-secondary inline-flex min-h-11 cursor-not-allowed items-center gap-2 rounded-lg px-4 text-sm font-semibold opacity-60"
            disabled
            title="Resume import is available in private workspaces; uploads are disabled in this shared demo."
            type="button"
          >
            <FileUp className="size-4" />
            Import resume
          </button>
        ) : (
          <div className="flex gap-2">
            <label className="cozy-button-secondary inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-lg px-4 text-sm font-semibold">
              {isImporting ? <LoaderCircle className="size-4 animate-spin" /> : <FileUp className="size-4" />}
              Import resume
              <input accept=".pdf,.docx" className="sr-only" disabled={isImporting || isSaving} onChange={handleResumeImport} type="file" />
            </label>
            <button
              type="button"
              aria-label="New candidate profile"
              onClick={beginCreate}
              disabled={isSaving || isImporting}
              className="cozy-button inline-flex min-h-11 items-center gap-2 rounded-lg px-4 text-sm font-semibold transition disabled:opacity-60"
            >
              <Plus className="size-4" />
              Add profile
            </button>
          </div>
        )}
      </div>

      {errorMessage && <p className="mt-3 text-xs leading-relaxed text-destructive">{errorMessage}</p>}
      {successMessage && <p className="mt-3 text-xs leading-relaxed text-primary">{successMessage}</p>}
      {IS_EXTERNAL_PREVIEW && (
        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
          Resume uploads and profile changes are disabled in this shared demo. Private workspaces can import PDF or DOCX data into the editable profile form before saving.
        </p>
      )}
      {importWarnings.length > 0 && (
        <div className="mt-3 rounded-md border border-brand-amber/35 bg-brand-amber/5 px-3 py-2 text-xs text-muted-foreground" role="status">
          {importWarnings.map((warning) => <p key={warning}>{warning}</p>)}
        </div>
      )}

      {mode === 'view' ? (
        <ProfileView
          profile={profile}
          isLoading={isLoading}
          readOnly={IS_EXTERNAL_PREVIEW}
          onEdit={beginEdit}
          onDelete={handleDelete}
        />
      ) : (
        <ProfileForm
          mode={mode}
          form={form}
          fieldErrors={fieldErrors}
          isSaving={isSaving}
          onChange={setForm}
          onCancel={() => { setMode('view'); setImportWarnings([]); }}
          onSubmit={handleSave}
        />
      )}
    </div>
  );
}

function ProfileView({
  profile,
  isLoading,
  readOnly,
  onEdit,
  onDelete,
}: {
  profile: CandidateProfile | null;
  isLoading: boolean;
  readOnly: boolean;
  onEdit: () => void;
  onDelete: () => void;
}) {
  if (isLoading) {
    return <p className="mt-5 flex items-center gap-2 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />Loading profile...</p>;
  }
  if (!profile) {
    return <p className="mt-5 text-sm text-muted-foreground">Create a candidate profile to start tailoring resumes.</p>;
  }

  const links = [
    ['LinkedIn', profile.linkedin_url],
    ['GitHub', profile.github_url],
    ['Portfolio', profile.portfolio_url],
  ].filter((item): item is [string, string] => Boolean(item[1]));

  return (
    <div className="cozy-panel-soft mt-5 rounded-xl p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-xl font-semibold text-foreground">{profile.full_name}</h3>
          {profile.headline && <p className="mt-1 text-sm text-muted-foreground">{profile.headline}</p>}
          <p className="mt-2 text-xs text-muted-foreground">
            {[profile.email, profile.phone, profile.location].filter(Boolean).join(' / ')}
          </p>
        </div>
        {!readOnly && (
          <div className="flex gap-2">
            <IconButton label="Edit profile" onClick={onEdit}><Pencil className="size-4" /></IconButton>
            <IconButton label="Delete profile" onClick={onDelete} destructive><Trash2 className="size-4" /></IconButton>
          </div>
        )}
      </div>
      {links.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-3">
          {links.map(([label, url]) => (
            <a key={label} href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-xs text-brand-amber hover:underline">
              {label}<ExternalLink className="size-3.5" />
            </a>
          ))}
        </div>
      )}
      {profile.summary && <p className="mt-4 line-clamp-3 text-sm leading-relaxed text-muted-foreground">{profile.summary}</p>}

      <details className="mt-4 border-t border-border pt-3">
        <summary className="cursor-pointer text-sm font-medium text-primary">
          View full candidate evidence
        </summary>
        <ProfileSection title="Skills">
          {profile.skills.length ? <div className="flex flex-wrap gap-2">{profile.skills.map((skill) => <Tag key={skill.id}>{skill.name}</Tag>)}</div> : <EmptyValue />}
        </ProfileSection>
        <ProfileSection title="Experience" icon={<BriefcaseBusiness className="size-4" />}>
          {profile.work_experiences.length ? profile.work_experiences.map((item) => <RecordLine key={item.id} title={item.job_title} meta={`${item.company} / ${formatDateRange(item.start_date, item.end_date)}`} description={item.description} />) : <EmptyValue />}
        </ProfileSection>
        <ProfileSection title="Projects">
          {profile.projects.length ? profile.projects.map((item) => <RecordLine key={item.id} title={item.title} meta={item.technologies.join(', ')} description={item.description} />) : <EmptyValue />}
        </ProfileSection>
        <ProfileSection title="Certifications">
          {profile.certifications.length ? profile.certifications.map((item) => <RecordLine key={item.id} title={item.name} meta={`${item.issuing_organization}${item.issue_date ? ` / ${item.issue_date.slice(0, 4)}` : ''}`} />) : <EmptyValue />}
        </ProfileSection>
        <ProfileSection title="Education" icon={<GraduationCap className="size-4" />}>
          {profile.education.length ? profile.education.map((item) => <RecordLine key={item.id} title={item.degree} meta={`${item.institution}${item.end_date ? ` / ${item.end_date.slice(0, 4)}` : ''}`} />) : <EmptyValue />}
        </ProfileSection>
      </details>
    </div>
  );
}

function ProfileForm({
  mode,
  form,
  fieldErrors,
  isSaving,
  onChange,
  onCancel,
  onSubmit,
}: {
  mode: 'create' | 'edit';
  form: ProfileFormState;
  fieldErrors: FieldErrors;
  isSaving: boolean;
  onChange: (form: ProfileFormState) => void;
  onCancel: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const setField = (field: keyof ProfileFormState, value: ProfileFormState[keyof ProfileFormState]) => onChange({...form, [field]: value});

  return (
    <form className="mt-6 space-y-8" onSubmit={onSubmit}>
      <FormSection title="Basic information">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Full name" value={form.fullName} onChange={(value) => setField('fullName', value)} error={fieldErrors.fullName} required />
          <FormField label="Email" type="email" value={form.email} onChange={(value) => setField('email', value)} error={fieldErrors.email} />
          <FormField label="Phone number" value={form.phone} onChange={(value) => setField('phone', value)} />
          <FormField label="Location" value={form.location} onChange={(value) => setField('location', value)} />
          <FormField label="LinkedIn URL" type="url" value={form.linkedinUrl} onChange={(value) => setField('linkedinUrl', value)} error={fieldErrors.linkedinUrl} />
          <FormField label="GitHub URL" type="url" value={form.githubUrl} onChange={(value) => setField('githubUrl', value)} error={fieldErrors.githubUrl} />
          <FormField label="Portfolio URL" type="url" value={form.portfolioUrl} onChange={(value) => setField('portfolioUrl', value)} error={fieldErrors.portfolioUrl} />
        </div>
      </FormSection>

      <FormSection title="Professional information">
        <FormField label="Professional headline" value={form.headline} onChange={(value) => setField('headline', value)} />
        <FormTextArea label="Professional summary" value={form.summary} onChange={(value) => setField('summary', value)} />
      </FormSection>

      <DynamicSection title="Skills" onAdd={() => setField('skills', [...form.skills, {name: '', category: 'General'}])}>
        {form.skills.map((skill, index) => (
          <DynamicRow key={`skill-${index}`} onRemove={() => setField('skills', removeAt(form.skills, index))}>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Skill" value={skill.name} onChange={(value) => setField('skills', replaceAt(form.skills, index, {...skill, name: value}))} error={fieldErrors[`skills.${index}.name`]} required />
              <FormField label="Category" value={skill.category} onChange={(value) => setField('skills', replaceAt(form.skills, index, {...skill, category: value}))} required />
            </div>
          </DynamicRow>
        ))}
      </DynamicSection>

      <DynamicSection title="Certifications" onAdd={() => setField('certifications', [...form.certifications, {name: '', organization: '', year: ''}])}>
        {form.certifications.map((item, index) => (
          <DynamicRow key={`certification-${index}`} onRemove={() => setField('certifications', removeAt(form.certifications, index))}>
            <div className="grid gap-4 sm:grid-cols-3">
              <FormField label="Certification name" value={item.name} onChange={(value) => setField('certifications', replaceAt(form.certifications, index, {...item, name: value}))} required />
              <FormField label="Organization" value={item.organization} onChange={(value) => setField('certifications', replaceAt(form.certifications, index, {...item, organization: value}))} required />
              <FormField label="Year" type="number" value={item.year} onChange={(value) => setField('certifications', replaceAt(form.certifications, index, {...item, year: value}))} error={fieldErrors[`certifications.${index}.year`]} />
            </div>
          </DynamicRow>
        ))}
      </DynamicSection>

      <DynamicSection title="Projects" onAdd={() => setField('projects', [...form.projects, {name: '', description: '', technologies: ''}])}>
        {form.projects.map((item, index) => (
          <DynamicRow key={`project-${index}`} onRemove={() => setField('projects', removeAt(form.projects, index))}>
            <FormField label="Project name" value={item.name} onChange={(value) => setField('projects', replaceAt(form.projects, index, {...item, name: value}))} required />
            <FormTextArea label="Description" value={item.description} onChange={(value) => setField('projects', replaceAt(form.projects, index, {...item, description: value}))} required />
            <FormField label="Technologies (comma separated)" value={item.technologies} onChange={(value) => setField('projects', replaceAt(form.projects, index, {...item, technologies: value}))} />
          </DynamicRow>
        ))}
      </DynamicSection>

      <DynamicSection title="Work experience" onAdd={() => setField('experiences', [...form.experiences, {jobTitle: '', company: '', startDate: '', endDate: '', description: ''}])}>
        {form.experiences.map((item, index) => (
          <DynamicRow key={`experience-${index}`} onRemove={() => setField('experiences', removeAt(form.experiences, index))}>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Job title" value={item.jobTitle} onChange={(value) => setField('experiences', replaceAt(form.experiences, index, {...item, jobTitle: value}))} required />
              <FormField label="Company" value={item.company} onChange={(value) => setField('experiences', replaceAt(form.experiences, index, {...item, company: value}))} required />
              <FormField label="Start date" type="date" value={item.startDate} onChange={(value) => setField('experiences', replaceAt(form.experiences, index, {...item, startDate: value}))} error={fieldErrors[`experiences.${index}.startDate`]} required />
              <FormField label="End date" type="date" value={item.endDate} onChange={(value) => setField('experiences', replaceAt(form.experiences, index, {...item, endDate: value}))} error={fieldErrors[`experiences.${index}.endDate`]} />
            </div>
            <FormTextArea label="Description" value={item.description} onChange={(value) => setField('experiences', replaceAt(form.experiences, index, {...item, description: value}))} />
          </DynamicRow>
        ))}
      </DynamicSection>

      <DynamicSection title="Education" onAdd={() => setField('education', [...form.education, {degree: '', institution: '', year: ''}])}>
        {form.education.map((item, index) => (
          <DynamicRow key={`education-${index}`} onRemove={() => setField('education', removeAt(form.education, index))}>
            <div className="grid gap-4 sm:grid-cols-3">
              <FormField label="Degree" value={item.degree} onChange={(value) => setField('education', replaceAt(form.education, index, {...item, degree: value}))} required />
              <FormField label="Institution" value={item.institution} onChange={(value) => setField('education', replaceAt(form.education, index, {...item, institution: value}))} required />
              <FormField label="Year" type="number" value={item.year} onChange={(value) => setField('education', replaceAt(form.education, index, {...item, year: value}))} error={fieldErrors[`education.${index}.year`]} />
            </div>
          </DynamicRow>
        ))}
      </DynamicSection>

      <div className="flex flex-wrap gap-3">
        <button type="submit" disabled={isSaving} className="cozy-button inline-flex min-h-11 items-center gap-2 rounded-lg px-5 text-sm font-semibold transition disabled:opacity-60">
          {isSaving ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
          {isSaving ? 'Saving profile' : mode === 'create' ? 'Create profile' : 'Save changes'}
        </button>
        <button type="button" onClick={onCancel} disabled={isSaving} className="cozy-button-secondary inline-flex min-h-11 items-center gap-2 rounded-lg px-5 text-sm transition disabled:opacity-60">
          <X className="size-4" />Cancel
        </button>
      </div>
    </form>
  );
}

function FormSection({title, children}: {title: string; children: ReactNode}) {
  return <section><h4 className="cozy-label mb-4">{title}</h4><div className="space-y-4">{children}</div></section>;
}

function DynamicSection({title, onAdd, children}: {title: string; onAdd: () => void; children: ReactNode}) {
  return (
    <section>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h4 className="cozy-label">{title}</h4>
        <button type="button" onClick={onAdd} aria-label={title === 'Skills' ? 'Add competency' : `Add ${title.toLowerCase()}`} className="inline-flex items-center gap-1.5 text-xs font-medium text-foreground hover:text-brand-amber"><Plus className="size-4" />Add</button>
      </div>
      <div className="space-y-4">{children}</div>
    </section>
  );
}

function DynamicRow({children, onRemove}: {children: ReactNode; onRemove: () => void; key?: string}) {
  return (
    <div className="cozy-panel-soft relative space-y-4 rounded-lg p-4 pr-12">
      {children}
      <button type="button" onClick={onRemove} aria-label="Remove item" title="Remove item" className="absolute right-3 top-3 text-muted-foreground transition hover:text-destructive"><Trash2 className="size-4" /></button>
    </div>
  );
}

function FormField({label, value, onChange, type = 'text', required = false, error}: {label: string; value: string; onChange: (value: string) => void; type?: string; required?: boolean; error?: string}) {
  return <label className="block"><span className="mb-2 block text-xs font-medium text-muted-foreground">{label}</span><input type={type} required={required} value={value} onChange={(event) => onChange(event.target.value)} aria-invalid={Boolean(error)} className={`cozy-field w-full rounded-lg px-3 py-2.5 text-sm text-foreground outline-none transition ${error ? 'border-destructive focus:border-destructive focus:ring-destructive/20' : ''}`} />{error && <span className="mt-1.5 block text-xs text-destructive">{error}</span>}</label>;
}

function FormTextArea({label, value, onChange, required = false}: {label: string; value: string; onChange: (value: string) => void; required?: boolean}) {
  return <label className="block"><span className="mb-2 block text-xs font-medium text-muted-foreground">{label}</span><textarea required={required} rows={4} value={value} onChange={(event) => onChange(event.target.value)} className="cozy-field w-full resize-y rounded-lg px-3 py-2.5 text-sm text-foreground outline-none transition" /></label>;
}

function ProfileSection({title, icon, children}: {title: string; icon?: ReactNode; children: ReactNode}) {
  return <div className="mt-5 border-t border-border/60 pt-4"><div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand-amber">{icon}{title}</div><div className="space-y-3">{children}</div></div>;
}

function RecordLine({title, meta, description}: {title: string; meta?: string; description?: string | null; key?: string}) {
  return <div><p className="text-sm font-medium text-foreground">{title}</p>{meta && <p className="mt-0.5 text-xs text-muted-foreground">{meta}</p>}{description && <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{description}</p>}</div>;
}

function Tag({children}: {children: ReactNode; key?: string}) {
  return <span className="rounded-full border border-border/70 bg-secondary/40 px-2.5 py-1 text-xs text-foreground">{children}</span>;
}

function EmptyValue() {
  return <p className="text-xs text-muted-foreground">No records added.</p>;
}

function IconButton({label, onClick, destructive = false, children}: {label: string; onClick: () => void; destructive?: boolean; children: ReactNode}) {
  return <button type="button" onClick={onClick} aria-label={label} title={label} className={`inline-flex size-9 items-center justify-center rounded-full border border-border transition ${destructive ? 'text-muted-foreground hover:border-destructive hover:text-destructive' : 'text-foreground hover:border-primary hover:text-primary'}`}>{children}</button>;
}

function formToPayload(form: ProfileFormState): CandidateProfileInput {
  return {
    full_name: form.fullName.trim(),
    email: nullable(form.email),
    phone: nullable(form.phone),
    location: nullable(form.location),
    linkedin_url: nullable(form.linkedinUrl),
    github_url: nullable(form.githubUrl),
    portfolio_url: nullable(form.portfolioUrl),
    headline: nullable(form.headline),
    summary: nullable(form.summary),
    skills: form.skills.filter((item) => item.name.trim()).map((item) => ({name: item.name.trim(), category: item.category.trim() || 'General', self_rating: 3, years_of_experience: 0})),
    certifications: form.certifications.map((item) => ({name: item.name.trim(), issuing_organization: item.organization.trim(), ...(item.year ? {issue_date: `${item.year}-01-01`} : {})})),
    projects: form.projects.map((item) => ({title: item.name.trim(), description: item.description.trim(), technologies: splitValues(item.technologies)})),
    work_experiences: form.experiences.map((item) => ({job_title: item.jobTitle.trim(), company: item.company.trim(), start_date: item.startDate, ...(item.endDate ? {end_date: item.endDate} : {}), is_current: !item.endDate, description: nullable(item.description)})),
    education: form.education.map((item) => ({degree: item.degree.trim(), institution: item.institution.trim(), ...(item.year ? {end_date: `${item.year}-12-31`} : {})})),
  };
}

function profileToForm(profile: CandidateProfile): ProfileFormState {
  return {
    fullName: profile.full_name,
    email: profile.email ?? '',
    phone: profile.phone ?? '',
    location: profile.location ?? '',
    linkedinUrl: profile.linkedin_url ?? '',
    githubUrl: profile.github_url ?? '',
    portfolioUrl: profile.portfolio_url ?? '',
    headline: profile.headline ?? '',
    summary: profile.summary ?? '',
    skills: profile.skills.map((item) => ({name: item.name, category: item.category})),
    certifications: profile.certifications.map((item) => ({name: item.name, organization: item.issuing_organization, year: item.issue_date?.slice(0, 4) ?? ''})),
    projects: profile.projects.map((item) => ({name: item.title, description: item.description, technologies: item.technologies.join(', ')})),
    experiences: profile.work_experiences.map((item) => ({jobTitle: item.job_title, company: item.company, startDate: item.start_date, endDate: item.end_date ?? '', description: item.description ?? ''})),
    education: profile.education.map((item) => ({degree: item.degree, institution: item.institution, year: (item.end_date ?? item.start_date)?.slice(0, 4) ?? ''})),
  };
}

function profileInputToForm(profile: CandidateProfileInput): ProfileFormState {
  return {
    fullName: profile.full_name,
    email: profile.email ?? '',
    phone: profile.phone ?? '',
    location: profile.location ?? '',
    linkedinUrl: profile.linkedin_url ?? '',
    githubUrl: profile.github_url ?? '',
    portfolioUrl: profile.portfolio_url ?? '',
    headline: profile.headline ?? '',
    summary: profile.summary ?? '',
    skills: profile.skills.map((item) => ({name: item.name, category: item.category})),
    certifications: profile.certifications.map((item) => ({name: item.name, organization: item.issuing_organization, year: item.issue_date?.slice(0, 4) ?? ''})),
    projects: profile.projects.map((item) => ({name: item.title, description: item.description, technologies: item.technologies.join(', ')})),
    experiences: profile.work_experiences.map((item) => ({jobTitle: item.job_title, company: item.company, startDate: item.start_date, endDate: item.end_date ?? '', description: item.description ?? ''})),
    education: profile.education.map((item) => ({degree: item.degree, institution: item.institution, year: item.end_date?.slice(0, 4) ?? ''})),
  };
}

function cloneEmptyForm(): ProfileFormState {
  return {...EMPTY_FORM, skills: [], certifications: [], projects: [], experiences: [], education: []};
}

function replaceAt<T>(items: T[], index: number, value: T): T[] {
  return items.map((item, itemIndex) => itemIndex === index ? value : item);
}

function removeAt<T>(items: T[], index: number): T[] {
  return items.filter((_, itemIndex) => itemIndex !== index);
}

function nullable(value: string): string | null {
  return value.trim() || null;
}

function splitValues(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function formatDateRange(start: string, end: string | null): string {
  return `${start.slice(0, 4)} - ${end ? end.slice(0, 4) : 'Present'}`;
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function validateProfileForm(form: ProfileFormState): FieldErrors {
  const errors: FieldErrors = {};
  if (!form.fullName.trim()) errors.fullName = 'Full name is required.';
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
    errors.email = 'Enter a valid email address.';
  }
  validateUrl(form.linkedinUrl, 'linkedinUrl', errors);
  validateUrl(form.githubUrl, 'githubUrl', errors);
  validateUrl(form.portfolioUrl, 'portfolioUrl', errors);

  const seenSkills = new Map<string, number>();
  form.skills.forEach((skill, index) => {
    const normalized = skill.name.trim().toLocaleLowerCase();
    if (!normalized) return;
    const duplicateIndex = seenSkills.get(normalized);
    if (duplicateIndex !== undefined) {
      errors[`skills.${index}.name`] = 'This skill is already listed.';
      errors[`skills.${duplicateIndex}.name`] = 'This skill is listed more than once.';
    } else {
      seenSkills.set(normalized, index);
    }
  });

  form.certifications.forEach((item, index) => validateYear(item.year, `certifications.${index}.year`, errors));
  form.education.forEach((item, index) => validateYear(item.year, `education.${index}.year`, errors));
  form.experiences.forEach((item, index) => {
    if (item.startDate && item.endDate && item.endDate < item.startDate) {
      errors[`experiences.${index}.endDate`] = 'End date cannot be before the start date.';
    }
  });
  return errors;
}

function validateUrl(value: string, key: string, errors: FieldErrors): void {
  if (!value.trim()) return;
  try {
    const url = new URL(value.trim());
    if (!['http:', 'https:'].includes(url.protocol)) throw new Error('unsupported protocol');
  } catch {
    errors[key] = 'Enter a complete http:// or https:// URL.';
  }
}

function validateYear(value: string, key: string, errors: FieldErrors): void {
  if (!value) return;
  const year = Number(value);
  const maximumYear = new Date().getFullYear() + 10;
  if (!/^\d{4}$/.test(value) || year < 1900 || year > maximumYear) {
    errors[key] = `Enter a four-digit year from 1900 to ${maximumYear}.`;
  }
}

function getApiFieldErrors(error: unknown): FieldErrors {
  if (!(error instanceof ApiError) || !Array.isArray(error.details)) return {};
  const errors: FieldErrors = {};
  for (const detail of error.details) {
    if (!detail || typeof detail !== 'object') continue;
    const record = detail as {loc?: unknown[]; msg?: string};
    const path = (record.loc ?? []).filter((part) => part !== 'body').join('.');
    const mappedPath = path
      .replace('full_name', 'fullName')
      .replace('linkedin_url', 'linkedinUrl')
      .replace('github_url', 'githubUrl')
      .replace('portfolio_url', 'portfolioUrl')
      .replace('work_experiences', 'experiences');
    if (mappedPath && record.msg) errors[mappedPath] = record.msg;
  }
  return errors;
}
