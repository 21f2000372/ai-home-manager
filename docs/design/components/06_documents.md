# Household Documents Component

## Story coverage

- US-6.1: upload bills, warranties, receipts, photos, and PDFs.
- US-4.1: parse a receipt and link it to an expense.
- US-5.2: support warranty evidence and reminders.

## Component diagram

```plantuml
@startuml
skinparam componentStyle uml2
skinparam shadowing false

component "Document API" as Api
component "Document Application" as DocumentApp
component "OCR / Extraction Port" as Extraction
component "Document Authorization" as Authorization
component "Document Repository Adapter" as Repository
component "Object Storage Adapter" as Storage
component "Tenant Isolation Policy" as TenantPolicy
database "Document Metadata Store" as Store
interface "Document Commands" as DocumentCommands
interface "Document Queries" as DocumentQueries
interface "Membership Queries" as Membership
interface "Domain Record Link" as DomainLink
interface "Tenant Context" as TenantContext

Api ..> DocumentCommands : requires
Api ..> DocumentQueries : requires
DocumentApp - DocumentCommands : provides
DocumentApp - DocumentQueries : provides
DocumentApp ..> Authorization : applies
DocumentApp ..> Membership : requires
DocumentApp ..> TenantContext : requires active household
DocumentApp ..> Extraction : classifies / parses
DocumentApp ..> DomainLink : links classified records
DocumentApp ..> Repository : persists metadata
DocumentApp ..> Storage : stores private binary
Repository ..> Store
TenantPolicy ..> Store : tenant-scoped metadata

note right of Authorization
  Documents are private by default.
  Household membership and role are
  checked before metadata or file access.
end note
@enduml
```

## Responsibilities and rules

- `Upload Handler` validates file type and size, stores the binary privately, and creates metadata.
- `Classification Handler` identifies receipt, bill, warranty, or other household document and requests OCR/extraction through a port.
- `Document Link Handler` links parsed data to a domain record without owning that record.
- `Document Query Handler` applies household and role filtering to metadata and download access.

The component owns document metadata and storage references. It does not directly create expenses, maintenance records, or bills; it emits a classified-document command for the owning component.

## Tenant-aware class structure

```plantuml
@startuml
skinparam classAttributeIconSize 0

class Document {
  +documentId: UUID
  +tenantId: UUID
  +documentType: DocumentType
  +storageKey: String
  +linkedRecordId: UUID
}
class DocumentLink {
  +tenantId: UUID
  +linkedDomain: String
  +linkedRecordId: UUID
}
class TenantContext {
  +tenantId: UUID
  +userId: UUID
  +role: HouseholdRole
}
interface DocumentRepository {
  +find(tenantId: UUID, documentId: UUID): Document
  +save(document: Document)
}
interface ObjectStorage {
  +put(tenantId: UUID, content): String
  +get(tenantId: UUID, storageKey: String): Content
}
class DocumentService {
  +upload(context: TenantContext, content): Document
  +link(context: TenantContext, link: DocumentLink)
}
class DocumentAuthorization {
  +canRead(context: TenantContext, document: Document): Boolean
}
class ClassificationPolicy {
  +classify(content): DocumentType
}

Document "1" -- "0..1" DocumentLink
DocumentService ..> DocumentRepository
DocumentService ..> ObjectStorage
DocumentService ..> DocumentAuthorization
DocumentService ..> ClassificationPolicy
DocumentService ..> TenantContext
TenantContext ..> Document : scopes
TenantContext ..> DocumentLink : scopes
@enduml
```

Both document metadata and object-storage keys are tenant-scoped. The storage adapter must require `tenantId`, preventing a valid document key from one household being used to retrieve another household's file.

## Behavior diagram: upload and classify a document

```plantuml
@startuml
skinparam shadowing false
skinparam sequenceMessageAlign center

actor "Household member" as User
participant "Document API" as Api
participant "Document Authorization" as Authorization
participant "Document Service" as Service
participant "Object Storage" as Storage
participant "OCR / Classifier" as Classifier
participant "Document Repository" as Repository
participant "Domain Link Port" as Link

User -> Api: Upload file(TenantContext, content)
Api -> Authorization: Check tenant document permission
Authorization --> Api: allowed or denied
Api -> Storage: Put(tenantId, content)
Storage --> Api: private storageKey
Api -> Classifier: Classify and extract(content)
Classifier --> Api: type + extracted fields
Api -> Service: Create metadata(TenantContext, storageKey)
Service -> Repository: Save tenant-scoped Document
opt parsed record is linkable
  Service -> Link: Link(tenantId, domain, recordId)
  Link --> Service: link accepted
end
Service --> Api: documentId
Api --> User: Upload complete
@enduml
```

The tenant context controls both metadata persistence and binary storage. Classification may suggest a domain link, but the owning domain remains responsible for creating its record.

## Internal structure

```plantuml
@startuml
skinparam componentStyle uml2
skinparam shadowing false

component "Household Documents" as Boundary {
  component "Upload Service" as Upload
  component "Document Query Service" as Query
  component "Classification Service" as Classification
  component "Domain Link Service" as Link
  component "Document Aggregate" as Aggregate
  component "Document Authorization" as Authorization
  component "Document Port" as DocumentPort
  component "Domain Link Port" as LinkPort
  component "Document Events Port" as EventPort

  DocumentPort --> Upload
  DocumentPort --> Query
  DocumentPort --> Classification
  DocumentPort --> Link
  Upload --> Authorization
  Query --> Authorization
  Link --> Authorization
  Upload --> Aggregate
  Query --> Aggregate
  Classification --> Aggregate
  Link --> Aggregate
  Aggregate --> LinkPort
  Aggregate --> EventPort
}
interface "Document Commands and Queries" as Contract
interface "Domain Record Link" as DomainLink
interface "Document Events" as Events
Contract --> Boundary.DocumentPort
Boundary.LinkPort --> DomainLink
Boundary.EventPort --> Events
@enduml
```

The internal structure separates upload, querying, classification, and linking. Storage and OCR remain replaceable adapters behind the public document port and are not allowed to create domain records directly.
